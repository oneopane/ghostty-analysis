from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from ...exports.area import area_for_path, load_repo_area_overrides
from ...paths import repo_db_path
from ...time import dt_sql_utc, require_dt_utc
from ..config import AreaMembershipConfig


@dataclass(frozen=True)
class UserAreaMatrix:
    users: list[str]
    areas: list[str]
    values: list[list[float]]


def pr_area_distribution_from_paths(
    *,
    repo: str,
    paths: list[str],
    data_dir: str | Path = "data",
) -> dict[str, float]:
    overrides = load_repo_area_overrides(repo_full_name=repo, data_dir=data_dir)
    counts: Counter[str] = Counter(area_for_path(p, overrides=overrides) for p in paths)
    total = float(sum(counts.values()))
    if total <= 0:
        return {}
    out = {k: float(v) / total for k, v in counts.items()}
    return {k: out[k] for k in sorted(out)}


def build_user_area_activity_rows(
    *,
    repo: str,
    cutoff: datetime,
    data_dir: str | Path = "data",
    config: AreaMembershipConfig | None = None,
) -> list[dict[str, Any]]:
    """Build user×area weighted activity rows for mixed-membership exploration.

    Output schema (deterministic order):
    - user_login (str)
    - area (str)
    - weight (float)
    """

    cfg = config or AreaMembershipConfig()
    cutoff_utc = require_dt_utc(cutoff, name="cutoff")
    start_utc = cutoff_utc - timedelta(days=cfg.lookback_days)

    db = repo_db_path(repo_full_name=repo, data_dir=data_dir)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row

    try:
        repo_row = conn.execute("select id from repos where full_name = ?", (repo,)).fetchone()
        if repo_row is None:
            raise KeyError(f"repo not found in db: {repo}")
        repo_id = int(repo_row["id"])

        start_s = dt_sql_utc(start_utc, timespec="seconds")
        cutoff_s = dt_sql_utc(cutoff_utc, timespec="seconds")

        activity_rows: list[tuple[str, str, int, str]] = []

        if cfg.include_authored:
            try:
                rows = conn.execute(
                    """
                    select lower(u.login) as login,
                           lower(coalesce(u.type, 'User')) as user_type,
                           pr.id as pr_id,
                           'authored' as kind
                    from pull_requests pr
                    join users u on u.id = pr.user_id
                    where pr.repo_id = ?
                      and pr.created_at is not null
                      and pr.created_at >= ?
                      and pr.created_at <= ?
                      and u.login is not null
                    """,
                    (repo_id, start_s, cutoff_s),
                ).fetchall()
                activity_rows.extend(
                    (str(r["login"]), str(r["user_type"]), int(r["pr_id"]), str(r["kind"]))
                    for r in rows
                )
            except sqlite3.OperationalError:
                pass

        if cfg.include_reviews:
            try:
                rows = conn.execute(
                    """
                    select lower(u.login) as login,
                           lower(coalesce(u.type, 'User')) as user_type,
                           r.pull_request_id as pr_id,
                           'review' as kind
                    from reviews r
                    join users u on u.id = r.user_id
                    where r.repo_id = ?
                      and r.submitted_at is not null
                      and r.submitted_at >= ?
                      and r.submitted_at <= ?
                      and r.pull_request_id is not null
                      and u.login is not null
                    """,
                    (repo_id, start_s, cutoff_s),
                ).fetchall()
                activity_rows.extend(
                    (str(r["login"]), str(r["user_type"]), int(r["pr_id"]), str(r["kind"]))
                    for r in rows
                )
            except sqlite3.OperationalError:
                pass

        if cfg.include_comments:
            try:
                rows = conn.execute(
                    """
                    select lower(u.login) as login,
                           lower(coalesce(u.type, 'User')) as user_type,
                           c.pull_request_id as pr_id,
                           'comment' as kind
                    from comments c
                    join users u on u.id = c.user_id
                    where c.repo_id = ?
                      and c.created_at is not null
                      and c.created_at >= ?
                      and c.created_at <= ?
                      and c.pull_request_id is not null
                      and u.login is not null
                    """,
                    (repo_id, start_s, cutoff_s),
                ).fetchall()
                activity_rows.extend(
                    (str(r["login"]), str(r["user_type"]), int(r["pr_id"]), str(r["kind"]))
                    for r in rows
                )
            except sqlite3.OperationalError:
                pass

        by_user_pr: dict[tuple[str, int], float] = defaultdict(float)
        for login, user_type, pr_id, kind in activity_rows:
            if cfg.exclude_bots and (user_type == "bot" or login.endswith("[bot]")):
                continue
            w = 0.0
            if kind == "authored":
                w = float(cfg.weight_authored)
            elif kind == "review":
                w = float(cfg.weight_review)
            elif kind == "comment":
                w = float(cfg.weight_comment)
            if w <= 0:
                continue
            by_user_pr[(login, pr_id)] += w

        pr_ids = sorted({pr_id for (_, pr_id) in by_user_pr})
        if not pr_ids:
            return []

        placeholders = ",".join("?" for _ in pr_ids)
        overrides = load_repo_area_overrides(repo_full_name=repo, data_dir=data_dir)

        by_pr_area_share: dict[int, dict[str, float]] = {}
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
                select lh.pr_id as pr_id,
                       pf.path as path,
                       pf.changes as changes
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

            by_pr_counter: dict[int, Counter[str]] = defaultdict(Counter)
            for r in rows:
                pr_id = int(r["pr_id"])
                path = str(r["path"])
                area = area_for_path(path, overrides=overrides)
                file_w = max(1.0, float(int(r["changes"] or 0)))
                by_pr_counter[pr_id][area] += file_w

            for pr_id, counter in by_pr_counter.items():
                total = float(sum(counter.values()))
                if total <= 0:
                    continue
                by_pr_area_share[pr_id] = {a: float(v) / total for a, v in counter.items()}
        except sqlite3.OperationalError:
            by_pr_area_share = {}

        by_user_area: dict[tuple[str, str], float] = defaultdict(float)
        for (login, pr_id), up_w in sorted(by_user_pr.items(), key=lambda kv: (kv[0][0], kv[0][1])):
            area_dist = by_pr_area_share.get(pr_id)
            if not area_dist:
                continue
            for area, p in area_dist.items():
                by_user_area[(login, area)] += float(up_w) * float(p)

        rows_out = [
            {
                "user_login": login,
                "area": area,
                "weight": float(weight),
            }
            for (login, area), weight in sorted(by_user_area.items(), key=lambda kv: (kv[0][0], kv[0][1]))
            if float(weight) > 0.0
        ]

        return rows_out
    finally:
        conn.close()


def build_user_area_activity_frame(
    *,
    repo: str,
    cutoff: datetime,
    data_dir: str | Path = "data",
    config: AreaMembershipConfig | None = None,
    engine: Literal["rows", "polars"] = "polars",
):
    """Notebook-friendly wrapper returning rows or a Polars DataFrame."""
    rows = build_user_area_activity_rows(
        repo=repo,
        cutoff=cutoff,
        data_dir=data_dir,
        config=config,
    )
    if engine == "rows":
        return rows

    try:
        import polars as pl  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover
        raise ImportError(
            "polars is required for engine='polars'. Install mixed-membership extras."
        ) from exc

    if rows:
        return pl.DataFrame(rows).sort(["user_login", "area"])
    return pl.DataFrame(schema={"user_login": pl.String, "area": pl.String, "weight": pl.Float64})


def rows_to_user_area_matrix(
    rows: list[dict[str, Any]],
    *,
    min_user_total_weight: float = 0.0,
) -> UserAreaMatrix:
    by_user_area: dict[tuple[str, str], float] = defaultdict(float)
    user_totals: dict[str, float] = defaultdict(float)

    for r in rows:
        user = str(r.get("user_login") or "").strip().lower()
        area = str(r.get("area") or "").strip()
        weight = float(r.get("weight") or 0.0)
        if not user or not area or weight <= 0.0:
            continue
        by_user_area[(user, area)] += weight
        user_totals[user] += weight

    users = sorted(
        [u for u, total in user_totals.items() if total >= float(min_user_total_weight)],
        key=str.lower,
    )
    areas = sorted({a for (_u, a) in by_user_area}, key=str.lower)

    user_ix = {u: i for i, u in enumerate(users)}
    area_ix = {a: j for j, a in enumerate(areas)}
    values = [[0.0 for _ in areas] for _ in users]

    for (u, a), w in sorted(by_user_area.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        i = user_ix.get(u)
        j = area_ix.get(a)
        if i is None or j is None:
            continue
        values[i][j] = float(w)

    return UserAreaMatrix(users=users, areas=areas, values=values)
