from __future__ import annotations

import fnmatch
import sqlite3
from collections import Counter
from datetime import timedelta
from pathlib import Path
from typing import Any

from ...exports.area import area_for_path, load_repo_area_overrides
from ...inputs.models import PRInputBundle
from .ownership import load_codeowners_text, parse_codeowners_rules
from .sql import connect_repo_db, cutoff_sql


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return float(inter) / float(union) if union > 0 else 0.0


def _dir_depth3(path: str) -> str:
    parts = [p for p in path.split("/") if p]
    if len(parts) <= 1:
        return "__root__"
    return "/".join(parts[: min(3, len(parts) - 1)])


def _churn_similarity(a: int, b: int) -> float:
    if a <= 0 and b <= 0:
        return 1.0
    m = max(a, b)
    if m <= 0:
        return 0.0
    return 1.0 - (abs(a - b) / float(m))


def _codeowners_match(pattern: str, path: str) -> bool:
    if pattern.endswith("/"):
        return path.startswith(pattern)
    if "*" in pattern or "?" in pattern or "[" in pattern:
        return fnmatch.fnmatch(path, pattern)
    return path == pattern or path.endswith(pattern.lstrip("/"))


def _owner_set_for_paths(*, repo: str, data_dir: str | Path, base_sha: str | None, paths: set[str]) -> set[str]:
    if not base_sha or not paths:
        return set()
    text = load_codeowners_text(repo=repo, base_sha=base_sha, data_dir=data_dir)
    if not text:
        return set()
    rules = parse_codeowners_rules(text)
    out: set[str] = set()
    for fp in sorted(paths):
        for r in rules:
            if _codeowners_match(r.pattern, fp):
                for t in r.targets:
                    out.add(t.name.lower())
    return out


def build_similarity_features(
    *,
    input: PRInputBundle,
    data_dir: str | Path,
    top_k: int = 5,
    lookback_days: int = 365,
) -> dict[str, Any]:
    conn = connect_repo_db(repo=input.repo, data_dir=data_dir)
    try:
        repo_row = conn.execute("select id from repos where full_name = ?", (input.repo,)).fetchone()
        if repo_row is None:
            return {
                "sim.nearest_prs.topk_ids": [],
                "sim.nearest_prs.mean_ttfr_topk": None,
                "sim.nearest_prs.owner_overlap_rate_topk": 0.0,
                "sim.nearest_prs.common_reviewers_topk": [],
                "sim.nearest_prs.common_areas_topk": [],
            }
        repo_id = int(repo_row["id"])
        ids = conn.execute(
            "select id from pull_requests where repo_id = ? and number = ?",
            (repo_id, input.pr_number),
        ).fetchone()
        current_pr_id = None if ids is None else int(ids["id"])

        start_s = cutoff_sql(input.cutoff - timedelta(days=lookback_days))
        cutoff_s = cutoff_sql(input.cutoff)
        owner_overlap_rate_topk = 0.0

        # Build candidate PR ids in lookback before or at cutoff.
        try:
            pr_rows = conn.execute(
                """
                select id, number, created_at, base_sha
                from pull_requests
                where repo_id = ?
                  and created_at is not null
                  and created_at >= ?
                  and created_at <= ?
                order by id asc
                """,
                (repo_id, start_s, cutoff_s),
            ).fetchall()
        except sqlite3.OperationalError:
            pr_rows = conn.execute(
                "select id, number, null as created_at, null as base_sha from pull_requests where repo_id = ? order by id asc",
                (repo_id,),
            ).fetchall()

        pr_base_sha: dict[int, str | None] = {int(r["id"]): r["base_sha"] for r in pr_rows}

        cand_rows = [r for r in pr_rows if int(r["id"]) != (current_pr_id or -1)]
        cand_ids = [int(r["id"]) for r in cand_rows]
        if not cand_ids:
            return {
                "sim.nearest_prs.topk_ids": [],
                "sim.nearest_prs.mean_ttfr_topk": None,
                "sim.nearest_prs.owner_overlap_rate_topk": 0.0,
                "sim.nearest_prs.common_reviewers_topk": [],
                "sim.nearest_prs.common_areas_topk": [],
            }

        placeholders = ",".join("?" for _ in cand_ids)

        # Load changed paths + churn for candidate PRs using latest head at cutoff.
        by_pr_paths: dict[int, set[str]] = {pid: set() for pid in cand_ids}
        by_pr_dirs: dict[int, set[str]] = {pid: set() for pid in cand_ids}
        by_pr_areas: dict[int, set[str]] = {pid: set() for pid in cand_ids}
        by_pr_churn: dict[int, int] = {pid: 0 for pid in cand_ids}

        overrides = load_repo_area_overrides(repo_full_name=input.repo, data_dir=data_dir)
        try:
            rows = conn.execute(
                f"""
                with latest_head as (
                  select phi.pull_request_id as pr_id,
                         phi.head_sha as head_sha,
                         row_number() over (
                            partition by phi.pull_request_id
                            order by se.occurred_at desc, se.id desc
                         ) as rn
                  from pull_request_head_intervals phi
                  join events se on se.id = phi.start_event_id
                  where se.occurred_at <= ?
                    and phi.pull_request_id in ({placeholders})
                )
                select lh.pr_id as pr_id, pf.path as path, pf.changes as changes
                from latest_head lh
                join pull_request_files pf
                  on pf.repo_id = ?
                 and pf.pull_request_id = lh.pr_id
                 and pf.head_sha = lh.head_sha
                where lh.rn = 1
                order by lh.pr_id asc, pf.path asc
                """,
                [cutoff_s, *cand_ids, repo_id],
            ).fetchall()
            for r in rows:
                pid = int(r["pr_id"])
                path = str(r["path"])
                by_pr_paths[pid].add(path)
                by_pr_dirs[pid].add(_dir_depth3(path))
                by_pr_areas[pid].add(area_for_path(path, overrides=overrides))
                by_pr_churn[pid] = by_pr_churn.get(pid, 0) + int(r["changes"] or 0)
        except sqlite3.OperationalError:
            pass

        # Current PR vectors.
        cur_paths = {f.path for f in input.changed_files}
        cur_dirs = {_dir_depth3(f.path) for f in input.changed_files}
        cur_areas = {a for a in input.file_areas.values() if a}
        cur_churn = sum(int(f.changes or 0) for f in input.changed_files)

        scored: list[tuple[float, int]] = []
        for pid in cand_ids:
            score = (
                0.45 * _jaccard(cur_paths, by_pr_paths.get(pid, set()))
                + 0.30 * _jaccard(cur_dirs, by_pr_dirs.get(pid, set()))
                + 0.15 * _jaccard(cur_areas, by_pr_areas.get(pid, set()))
                + 0.10 * _churn_similarity(cur_churn, by_pr_churn.get(pid, 0))
            )
            scored.append((score, pid))

        scored.sort(key=lambda x: (-x[0], x[1]))
        top = [pid for _s, pid in scored[:top_k]]
        if not top:
            return {
                "sim.nearest_prs.topk_ids": [],
                "sim.nearest_prs.mean_ttfr_topk": None,
                "sim.nearest_prs.owner_overlap_rate_topk": 0.0,
                "sim.nearest_prs.common_reviewers_topk": [],
                "sim.nearest_prs.common_areas_topk": [],
            }

        # TTFR for top-k.
        top_placeholders = ",".join("?" for _ in top)
        ttfr_vals: list[float] = []
        try:
            rows = conn.execute(
                f"""
                select pr.id as pr_id, pr.created_at as created_at, min(r.submitted_at) as first_review_at
                from pull_requests pr
                join reviews r
                  on r.repo_id = pr.repo_id
                 and r.pull_request_id = pr.id
                where pr.repo_id = ?
                  and pr.id in ({top_placeholders})
                  and pr.created_at is not null
                  and r.submitted_at is not null
                  and r.submitted_at <= ?
                group by pr.id, pr.created_at
                order by pr.id asc
                """,
                [repo_id, *top, cutoff_s],
            ).fetchall()
            from ...time import parse_dt_utc

            for r in rows:
                c = parse_dt_utc(r["created_at"])
                f = parse_dt_utc(r["first_review_at"])
                if c is None or f is None:
                    continue
                ttfr_vals.append(max(0.0, (f - c).total_seconds()))
        except sqlite3.OperationalError:
            ttfr_vals = []

        # Common reviewers and areas.
        reviewer_counter: Counter[str] = Counter()
        try:
            rows = conn.execute(
                f"""
                select lower(u.login) as login
                from reviews r
                join users u on u.id = r.user_id
                where r.repo_id = ?
                  and r.pull_request_id in ({top_placeholders})
                  and r.submitted_at <= ?
                  and u.login is not null
                order by lower(u.login) asc
                """,
                [repo_id, *top, cutoff_s],
            ).fetchall()
            for r in rows:
                reviewer_counter[str(r["login"]).lower()] += 1
        except sqlite3.OperationalError:
            pass

        area_counter: Counter[str] = Counter()
        for pid in top:
            for a in sorted(by_pr_areas.get(pid, set()), key=str.lower):
                area_counter[a] += 1

        top_reviewers = [k for k, _v in sorted(reviewer_counter.items(), key=lambda kv: (-kv[1], kv[0]))[:10]]
        top_areas = [k for k, _v in sorted(area_counter.items(), key=lambda kv: (-kv[1], kv[0].lower()))[:10]]

        current_owner_set = _owner_set_for_paths(
            repo=input.repo,
            data_dir=data_dir,
            base_sha=input.snapshot.base_sha,
            paths=cur_paths,
        )
        overlap_vals: list[float] = []
        for pid in top:
            other_owner_set = _owner_set_for_paths(
                repo=input.repo,
                data_dir=data_dir,
                base_sha=pr_base_sha.get(pid),
                paths=by_pr_paths.get(pid, set()),
            )
            overlap_vals.append(_jaccard(current_owner_set, other_owner_set))
        owner_overlap_rate_topk = (
            sum(overlap_vals) / float(len(overlap_vals)) if overlap_vals else 0.0
        )

    finally:
        conn.close()

    mean_ttfr = (sum(ttfr_vals) / float(len(ttfr_vals))) if ttfr_vals else None

    out: dict[str, Any] = {
        "sim.nearest_prs.topk_ids": top,
        "sim.nearest_prs.mean_ttfr_topk": mean_ttfr,
        "sim.nearest_prs.owner_overlap_rate_topk": owner_overlap_rate_topk,
        "sim.nearest_prs.common_reviewers_topk": top_reviewers,
        "sim.nearest_prs.common_areas_topk": top_areas,
    }
    return {k: out[k] for k in sorted(out)}
