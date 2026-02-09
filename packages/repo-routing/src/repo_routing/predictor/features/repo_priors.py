from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import timedelta
from pathlib import Path
from typing import Any

import fnmatch

from ...exports.area import area_for_path, load_repo_area_overrides
from ...inputs.models import PRInputBundle
from ...paths import repo_codeowners_path
from .ownership import parse_codeowners_rules
from .sql import connect_repo_db, cutoff_sql
from .stats import median_int


def _stddev(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / float(len(values))
    var = sum((v - mean) ** 2 for v in values) / float(len(values))
    return var ** 0.5


def _zscore(value: float, values: list[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / float(len(values))
    sd = _stddev(values)
    if sd <= 0.0:
        return 0.0
    return (value - mean) / sd


def _codeowners_match(pattern: str, path: str) -> bool:
    if pattern.endswith("/"):
        return path.startswith(pattern)
    if "*" in pattern or "?" in pattern or "[" in pattern:
        return fnmatch.fnmatch(path, pattern)
    return path == pattern or path.endswith(pattern.lstrip("/"))


def build_repo_priors_features(
    *,
    input: PRInputBundle,
    data_dir: str | Path,
    window_days: int = 180,
    area_top_n: int = 12,
) -> dict[str, Any]:
    conn = connect_repo_db(repo=input.repo, data_dir=data_dir)
    try:
        repo_row = conn.execute("select id from repos where full_name = ?", (input.repo,)).fetchone()
        if repo_row is None:
            return {}
        repo_id = int(repo_row["id"])

        start_s = cutoff_sql(input.cutoff - timedelta(days=window_days))
        cutoff_s = cutoff_sql(input.cutoff)

        # Pull candidate PR ids in window.
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
                """
                select id, number, null as created_at, null as base_sha
                from pull_requests
                where repo_id = ?
                order by id asc
                """,
                (repo_id,),
            ).fetchall()

        pr_ids = [int(r["id"]) for r in pr_rows]
        if not pr_ids:
            return {
                "repo.priors.median_pr_files_180d": 0.0,
                "repo.priors.median_pr_churn_180d": 0.0,
                "repo.priors.median_ttfr_180d": None,
                "repo.priors.owner_coverage_rate_180d": 0.0,
                "repo.priors.request_rate_180d": 0.0,
                "repo.priors.bot_activity_rate_180d": 0.0,
                "repo.priors.area_frequency.topN": {},
                "repo.priors.directory_hotspots.depth3.topN": {},
                "pr.surface.files_zscore_vs_repo": 0.0,
                "pr.surface.churn_zscore_vs_repo": 0.0,
            }

        placeholders = ",".join("?" for _ in pr_ids)
        pr_base_sha: dict[int, str | None] = {int(r["id"]): r["base_sha"] for r in pr_rows}

        # Latest head per PR as-of cutoff, then file aggregates.
        file_counts: list[float] = []
        churn_counts: list[float] = []
        area_counter: Counter[str] = Counter()
        dir_counter: Counter[str] = Counter()
        by_pr_paths: dict[int, list[str]] = {pid: [] for pid in pr_ids}
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
                [cutoff_s, *pr_ids, repo_id],
            ).fetchall()
            by_pr_files: dict[int, int] = {}
            by_pr_churn: dict[int, int] = {}
            overrides = load_repo_area_overrides(repo_full_name=input.repo, data_dir=data_dir)
            for r in rows:
                pr_id = int(r["pr_id"])
                by_pr_files[pr_id] = by_pr_files.get(pr_id, 0) + 1
                by_pr_churn[pr_id] = by_pr_churn.get(pr_id, 0) + int(r["changes"] or 0)
                path = str(r["path"])
                by_pr_paths.setdefault(pr_id, []).append(path)
                area_counter[area_for_path(path, overrides=overrides)] += 1
                parts = [p for p in path.split("/") if p]
                key = "__root__" if len(parts) <= 1 else "/".join(parts[: min(3, len(parts) - 1)])
                dir_counter[key] += 1

            file_counts = [float(by_pr_files.get(pid, 0)) for pid in pr_ids]
            churn_counts = [float(by_pr_churn.get(pid, 0)) for pid in pr_ids]
        except sqlite3.OperationalError:
            file_counts = []
            churn_counts = []

        # Request rate.
        request_prs = 0
        try:
            rr = conn.execute(
                f"""
                select count(distinct pull_request_id) as n
                from pull_request_review_request_intervals
                where pull_request_id in ({placeholders})
                """,
                pr_ids,
            ).fetchone()
            request_prs = 0 if rr is None else int(rr["n"])
        except sqlite3.OperationalError:
            request_prs = 0

        # Bot activity rate from comments + reviews.
        bot_total = 0
        total_events = 0
        try:
            row = conn.execute(
                f"""
                select
                  sum(case when lower(coalesce(u.type, 'User')) = 'bot' then 1 else 0 end) as bot_n,
                  count(*) as total_n
                from (
                  select c.user_id as uid
                  from comments c
                  where c.repo_id = ? and c.pull_request_id in ({placeholders}) and c.created_at <= ?
                  union all
                  select r.user_id as uid
                  from reviews r
                  where r.repo_id = ? and r.pull_request_id in ({placeholders}) and r.submitted_at <= ?
                ) ev
                join users u on u.id = ev.uid
                """,
                [repo_id, *pr_ids, cutoff_s, repo_id, *pr_ids, cutoff_s],
            ).fetchone()
            if row is not None:
                bot_total = int(row["bot_n"] or 0)
                total_events = int(row["total_n"] or 0)
        except sqlite3.OperationalError:
            bot_total = 0
            total_events = 0

        # Median ttfr.
        ttfr_vals: list[float] = []
        owner_coverage_vals: list[float] = []
        try:
            rows = conn.execute(
                f"""
                select pr.id as pr_id,
                       min(r.submitted_at) as first_review_at,
                       pr.created_at as created_at
                from pull_requests pr
                join reviews r
                  on r.repo_id = pr.repo_id
                 and r.pull_request_id = pr.id
                where pr.repo_id = ?
                  and pr.id in ({placeholders})
                  and r.submitted_at is not null
                  and r.submitted_at <= ?
                  and pr.created_at is not null
                group by pr.id, pr.created_at
                order by pr.id asc
                """,
                [repo_id, *pr_ids, cutoff_s],
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

        # CODEOWNERS-based owner coverage priors.
        try:
            for pid in pr_ids:
                paths = by_pr_paths.get(pid, [])
                if not paths:
                    continue
                base_sha = pr_base_sha.get(pid)
                if not base_sha:
                    continue
                codeowners_p = repo_codeowners_path(
                    repo_full_name=input.repo,
                    base_sha=base_sha,
                    data_dir=data_dir,
                )
                if not codeowners_p.exists():
                    continue
                rules = parse_codeowners_rules(codeowners_p.read_text(encoding="utf-8"))
                if not rules:
                    continue
                owned = 0
                for p in paths:
                    matched = False
                    for rule in rules:
                        if _codeowners_match(rule.pattern, p):
                            matched = True
                            break
                    if matched:
                        owned += 1
                owner_coverage_vals.append(float(owned) / float(len(paths)))
        except Exception:
            owner_coverage_vals = []

    finally:
        conn.close()

    area_total = float(sum(area_counter.values()))
    area_top = sorted(area_counter.items(), key=lambda kv: (-kv[1], kv[0].lower()))[:area_top_n]
    area_map = {k: (float(v) / area_total if area_total > 0 else 0.0) for k, v in area_top}

    dir_total = float(sum(dir_counter.values()))
    dir_top = sorted(dir_counter.items(), key=lambda kv: (-kv[1], kv[0].lower()))[:area_top_n]
    dir_map = {k: (float(v) / dir_total if dir_total > 0 else 0.0) for k, v in dir_top}

    current_files = float(len(input.changed_files))
    current_churn = float(sum(int(f.changes or 0) for f in input.changed_files))

    out: dict[str, Any] = {
        "repo.priors.median_pr_files_180d": median_int([int(v) for v in file_counts]) if file_counts else 0.0,
        "repo.priors.median_pr_churn_180d": median_int([int(v) for v in churn_counts]) if churn_counts else 0.0,
        "repo.priors.median_ttfr_180d": median_int([int(v) for v in ttfr_vals]) if ttfr_vals else None,
        "repo.priors.owner_coverage_rate_180d": (
            sum(owner_coverage_vals) / float(len(owner_coverage_vals)) if owner_coverage_vals else 0.0
        ),
        "repo.priors.request_rate_180d": float(request_prs) / float(len(pr_ids)) if pr_ids else 0.0,
        "repo.priors.bot_activity_rate_180d": float(bot_total) / float(total_events) if total_events > 0 else 0.0,
        "repo.priors.area_frequency.topN": {k: area_map[k] for k in sorted(area_map)},
        "repo.priors.directory_hotspots.depth3.topN": {k: dir_map[k] for k in sorted(dir_map)},
        "pr.surface.files_zscore_vs_repo": _zscore(current_files, file_counts),
        "pr.surface.churn_zscore_vs_repo": _zscore(current_churn, churn_counts),
    }

    return {k: out[k] for k in sorted(out)}
