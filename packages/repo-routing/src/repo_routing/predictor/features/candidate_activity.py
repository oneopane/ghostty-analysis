from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ...exports.area import area_for_path, load_repo_area_overrides
from ...inputs.models import PRInputBundle
from ...time import parse_dt_utc
from .sql import candidate_last_activity_and_counts, connect_repo_db, cutoff_sql
from .stats import normalized_entropy


def days_since_last_candidate_activity(
    *,
    repo: str,
    candidate_login: str,
    cutoff: datetime,
    data_dir: str | Path,
) -> float | None:
    conn = connect_repo_db(repo=repo, data_dir=data_dir)
    try:
        row = conn.execute("select id from repos where full_name = ?", (repo,)).fetchone()
        if row is None:
            raise KeyError(f"repo not found in db: {repo}")
        repo_id = int(row["id"])

        last_ts, _counts = candidate_last_activity_and_counts(
            conn=conn,
            repo_id=repo_id,
            candidate_login=candidate_login,
            cutoff=cutoff,
            windows_days=(30,),
        )
    finally:
        conn.close()

    if last_ts is None:
        return None
    return (cutoff - last_ts).total_seconds() / 86400.0


def candidate_event_volume_by_windows(
    *,
    repo: str,
    candidate_login: str,
    cutoff: datetime,
    windows_days: tuple[int, ...],
    data_dir: str | Path,
) -> dict[int, int]:
    conn = connect_repo_db(repo=repo, data_dir=data_dir)
    try:
        row = conn.execute("select id from repos where full_name = ?", (repo,)).fetchone()
        if row is None:
            raise KeyError(f"repo not found in db: {repo}")
        repo_id = int(row["id"])

        _last_ts, counts = candidate_last_activity_and_counts(
            conn=conn,
            repo_id=repo_id,
            candidate_login=candidate_login,
            cutoff=cutoff,
            windows_days=windows_days,
        )
        return counts
    finally:
        conn.close()


def _user_profile_row(
    *,
    repo: str,
    candidate_login: str,
    data_dir: str | Path,
) -> tuple[str, str | None]:
    conn = connect_repo_db(repo=repo, data_dir=data_dir)
    try:
        try:
            row = conn.execute(
                "select lower(coalesce(type, 'User')) as user_type, login from users where lower(login)=lower(?) limit 1",
                (candidate_login,),
            ).fetchone()
        except sqlite3.OperationalError:
            # Minimal test schemas may omit users.type.
            row = conn.execute(
                "select 'user' as user_type, login from users where lower(login)=lower(?) limit 1",
                (candidate_login,),
            ).fetchone()
    finally:
        conn.close()

    if row is None:
        return "user", None
    return str(row["user_type"]).lower(), row["login"]


def _candidate_account_age_days(
    *,
    repo: str,
    candidate_login: str,
    cutoff: datetime,
    data_dir: str | Path,
) -> float | None:
    conn = connect_repo_db(repo=repo, data_dir=data_dir)
    try:
        user = conn.execute(
            "select id from users where lower(login)=lower(?) limit 1",
            (candidate_login,),
        ).fetchone()
        repo_row = conn.execute("select id from repos where full_name = ?", (repo,)).fetchone()
        if user is None or repo_row is None:
            return None
        user_id = int(user["id"])
        repo_id = int(repo_row["id"])

        # Prefer users.created_at if present, otherwise derive from earliest seen event.
        created_at = None
        try:
            row = conn.execute(
                "select created_at from users where id = ?",
                (user_id,),
            ).fetchone()
            if row is not None:
                created_at = row["created_at"]
        except sqlite3.OperationalError:
            created_at = None

        if created_at is not None:
            ts = parse_dt_utc(created_at)
            if ts is not None:
                return max(0.0, (cutoff - ts).total_seconds() / 86400.0)

        row = conn.execute(
            """
            select min(ts) as first_ts from (
              select r.submitted_at as ts from reviews r where r.repo_id=? and r.user_id=? and r.submitted_at <= ?
              union all
              select c.created_at as ts from comments c where c.repo_id=? and c.user_id=? and c.created_at <= ?
              union all
              select e.occurred_at as ts from events e where e.repo_id=? and e.actor_id=? and e.occurred_at <= ?
            )
            """,
            (
                repo_id,
                user_id,
                cutoff_sql(cutoff),
                repo_id,
                user_id,
                cutoff_sql(cutoff),
                repo_id,
                user_id,
                cutoff_sql(cutoff),
            ),
        ).fetchone()
        if row is None or row["first_ts"] is None:
            return None
        first_ts = parse_dt_utc(row["first_ts"])
        if first_ts is None:
            return None
        return max(0.0, (cutoff - first_ts).total_seconds() / 86400.0)
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def _open_reviews_est(
    *,
    repo: str,
    candidate_login: str,
    cutoff: datetime,
    data_dir: str | Path,
) -> int | None:
    conn = connect_repo_db(repo=repo, data_dir=data_dir)
    try:
        repo_row = conn.execute("select id from repos where full_name = ?", (repo,)).fetchone()
        user_row = conn.execute("select id from users where lower(login)=lower(?)", (candidate_login,)).fetchone()
        if repo_row is None or user_row is None:
            return 0
        repo_id = int(repo_row["id"])
        user_id = int(user_row["id"])
        row = conn.execute(
            """
            select count(distinct rri.pull_request_id) as n
            from pull_request_review_request_intervals rri
            join pull_requests pr on pr.id = rri.pull_request_id and pr.repo_id = ?
            join events se on se.id = rri.start_event_id
            left join events ee on ee.id = rri.end_event_id
            where rri.reviewer_type = 'User'
              and rri.reviewer_id = ?
              and se.occurred_at <= ?
              and (ee.id is null or ? < ee.occurred_at)
            """,
            (repo_id, user_id, cutoff_sql(cutoff), cutoff_sql(cutoff)),
        ).fetchone()
        return 0 if row is None else int(row["n"] or 0)
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def _count_reviews_comments(
    *,
    repo: str,
    candidate_login: str,
    cutoff: datetime,
    window_days: int,
    data_dir: str | Path,
) -> tuple[int, int]:
    conn = connect_repo_db(repo=repo, data_dir=data_dir)
    try:
        repo_row = conn.execute("select id from repos where full_name = ?", (repo,)).fetchone()
        user_row = conn.execute("select id from users where lower(login) = lower(?)", (candidate_login,)).fetchone()
        if repo_row is None or user_row is None:
            return 0, 0
        repo_id = int(repo_row["id"])
        user_id = int(user_row["id"])
        start_s = cutoff_sql(cutoff - timedelta(days=window_days))
        cutoff_s = cutoff_sql(cutoff)
        reviews_row = conn.execute(
            """
            select count(*) as n
            from reviews r
            where r.repo_id = ? and r.user_id = ? and r.submitted_at >= ? and r.submitted_at <= ?
            """,
            (repo_id, user_id, start_s, cutoff_s),
        ).fetchone()
        comments_row = conn.execute(
            """
            select count(*) as n
            from comments c
            where c.repo_id = ? and c.user_id = ? and c.created_at >= ? and c.created_at <= ?
            """,
            (repo_id, user_id, start_s, cutoff_s),
        ).fetchone()
        return (
            0 if reviews_row is None else int(reviews_row["n"]),
            0 if comments_row is None else int(comments_row["n"]),
        )
    finally:
        conn.close()


def _count_authored_prs(
    *,
    repo: str,
    candidate_login: str,
    cutoff: datetime,
    window_days: int,
    data_dir: str | Path,
) -> int:
    conn = connect_repo_db(repo=repo, data_dir=data_dir)
    try:
        repo_row = conn.execute("select id from repos where full_name = ?", (repo,)).fetchone()
        user_row = conn.execute("select id from users where lower(login) = lower(?)", (candidate_login,)).fetchone()
        if repo_row is None or user_row is None:
            return 0
        try:
            row = conn.execute(
                """
                select count(*) as n
                from pull_requests pr
                where pr.repo_id = ?
                  and pr.user_id = ?
                  and pr.created_at is not null
                  and pr.created_at >= ?
                  and pr.created_at <= ?
                """,
                (
                    int(repo_row["id"]),
                    int(user_row["id"]),
                    cutoff_sql(cutoff - timedelta(days=window_days)),
                    cutoff_sql(cutoff),
                ),
            ).fetchone()
        except sqlite3.OperationalError:
            row = conn.execute(
                """
                select count(*) as n
                from pull_requests pr
                where pr.repo_id = ?
                  and pr.user_id = ?
                """,
                (int(repo_row["id"]), int(user_row["id"])),
            ).fetchone()
        return 0 if row is None else int(row["n"])
    finally:
        conn.close()


def _candidate_touched_pr_ids(
    *,
    repo: str,
    candidate_login: str,
    cutoff: datetime,
    window_days: int,
    data_dir: str | Path,
) -> list[int]:
    conn = connect_repo_db(repo=repo, data_dir=data_dir)
    try:
        repo_row = conn.execute("select id from repos where full_name = ?", (repo,)).fetchone()
        user_row = conn.execute("select id from users where lower(login) = lower(?)", (candidate_login,)).fetchone()
        if repo_row is None or user_row is None:
            return []
        repo_id = int(repo_row["id"])
        user_id = int(user_row["id"])
        start_s = cutoff_sql(cutoff - timedelta(days=window_days))
        cutoff_s = cutoff_sql(cutoff)
        try:
            rows = conn.execute(
                """
                select distinct pr_id from (
                  select r.pull_request_id as pr_id
                  from reviews r
                  where r.repo_id = ? and r.user_id = ? and r.submitted_at >= ? and r.submitted_at <= ?
                  union
                  select c.pull_request_id as pr_id
                  from comments c
                  where c.repo_id = ? and c.user_id = ? and c.created_at >= ? and c.created_at <= ?
                  union
                  select pr.id as pr_id
                  from pull_requests pr
                  where pr.repo_id = ? and pr.user_id = ? and pr.created_at >= ? and pr.created_at <= ?
                )
                where pr_id is not null
                order by pr_id asc
                """,
                (
                    repo_id,
                    user_id,
                    start_s,
                    cutoff_s,
                    repo_id,
                    user_id,
                    start_s,
                    cutoff_s,
                    repo_id,
                    user_id,
                    start_s,
                    cutoff_s,
                ),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = conn.execute(
                """
                select distinct pr_id from (
                  select r.pull_request_id as pr_id
                  from reviews r
                  where r.repo_id = ? and r.user_id = ? and r.submitted_at >= ? and r.submitted_at <= ?
                  union
                  select c.pull_request_id as pr_id
                  from comments c
                  where c.repo_id = ? and c.user_id = ? and c.created_at >= ? and c.created_at <= ?
                  union
                  select pr.id as pr_id
                  from pull_requests pr
                  where pr.repo_id = ? and pr.user_id = ?
                )
                where pr_id is not null
                order by pr_id asc
                """,
                (repo_id, user_id, start_s, cutoff_s, repo_id, user_id, start_s, cutoff_s, repo_id, user_id),
            ).fetchall()
        return [int(r["pr_id"]) for r in rows]
    finally:
        conn.close()


def _load_pr_paths_for_pr_ids(
    *,
    repo: str,
    pr_ids: list[int],
    cutoff: datetime,
    data_dir: str | Path,
) -> list[str]:
    if not pr_ids:
        return []
    conn = connect_repo_db(repo=repo, data_dir=data_dir)
    try:
        repo_row = conn.execute("select id from repos where full_name = ?", (repo,)).fetchone()
        if repo_row is None:
            return []
        repo_id = int(repo_row["id"])

        placeholders = ",".join("?" for _ in pr_ids)
        rows = conn.execute(
            f"""
            with latest_head as (
              select phi.pull_request_id as pr_id, phi.head_sha as head_sha,
                     row_number() over (
                        partition by phi.pull_request_id
                        order by se.occurred_at desc, se.id desc
                     ) as rn
              from pull_request_head_intervals phi
              join events se on se.id = phi.start_event_id
              where se.occurred_at <= ?
                and phi.pull_request_id in ({placeholders})
            )
            select pf.path as path
            from latest_head lh
            join pull_request_files pf
              on pf.repo_id = ?
             and pf.pull_request_id = lh.pr_id
             and pf.head_sha = lh.head_sha
            where lh.rn = 1
            order by pf.path asc
            """,
            [cutoff_sql(cutoff), *pr_ids, repo_id],
        ).fetchall()
        return [str(r["path"]) for r in rows if r["path"] is not None]
    except sqlite3.OperationalError:
        # For tiny test schemas without interval/files relation richness.
        return []
    finally:
        conn.close()


def _dir_depth3(path: str) -> str:
    parts = [p for p in path.split("/") if p]
    if len(parts) <= 1:
        return "__root__"
    return "/".join(parts[: min(3, len(parts) - 1)])


def _top_n_scores(counter: Counter[str], *, top_n: int) -> dict[str, float]:
    total = float(sum(counter.values()))
    if total <= 0:
        return {}
    pairs = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0].lower()))[:top_n]
    out = {k: float(v) / total for k, v in pairs}
    return {k: out[k] for k in sorted(out)}


def build_candidate_activity_features(
    *,
    input: PRInputBundle,
    candidate_login: str,
    data_dir: str | Path,
    windows_days: tuple[int, ...] = (7, 30, 90, 180),
    footprint_top_n: int = 12,
) -> dict[str, Any]:
    days_since = days_since_last_candidate_activity(
        repo=input.repo,
        candidate_login=candidate_login,
        cutoff=input.cutoff,
        data_dir=data_dir,
    )
    counts = candidate_event_volume_by_windows(
        repo=input.repo,
        candidate_login=candidate_login,
        cutoff=input.cutoff,
        windows_days=windows_days,
        data_dir=data_dir,
    )

    user_type, canonical_login = _user_profile_row(
        repo=input.repo,
        candidate_login=candidate_login,
        data_dir=data_dir,
    )
    is_bot = user_type.lower() == "bot" or candidate_login.lower().endswith("[bot]")

    review_count_180d, comment_count_180d = _count_reviews_comments(
        repo=input.repo,
        candidate_login=candidate_login,
        cutoff=input.cutoff,
        window_days=180,
        data_dir=data_dir,
    )
    authored_pr_180d = _count_authored_prs(
        repo=input.repo,
        candidate_login=candidate_login,
        cutoff=input.cutoff,
        window_days=180,
        data_dir=data_dir,
    )

    touched_pr_ids = _candidate_touched_pr_ids(
        repo=input.repo,
        candidate_login=candidate_login,
        cutoff=input.cutoff,
        window_days=180,
        data_dir=data_dir,
    )
    touched_paths = _load_pr_paths_for_pr_ids(
        repo=input.repo,
        pr_ids=touched_pr_ids,
        cutoff=input.cutoff,
        data_dir=data_dir,
    )

    overrides = load_repo_area_overrides(repo_full_name=input.repo, data_dir=data_dir)
    areas = [area_for_path(p, overrides=overrides) for p in touched_paths]
    dirs3 = [_dir_depth3(p) for p in touched_paths]

    area_counts = Counter(areas)
    dir_counts = Counter(dirs3)
    path_counts = Counter(touched_paths)

    account_age_days = _candidate_account_age_days(
        repo=input.repo,
        candidate_login=candidate_login,
        cutoff=input.cutoff,
        data_dir=data_dir,
    )
    open_reviews_est = _open_reviews_est(
        repo=input.repo,
        candidate_login=candidate_login,
        cutoff=input.cutoff,
        data_dir=data_dir,
    )

    login_features: list[str] = []
    if candidate_login.lower().endswith("[bot]"):
        login_features.append("bot_suffix")
    if "-" in candidate_login:
        login_features.append("has_dash")
    if any(ch.isdigit() for ch in candidate_login):
        login_features.append("has_digit")

    out: dict[str, Any] = {
        # E1 profile
        "candidate.profile.type": "user",
        "candidate.profile.is_bot": is_bot,
        "candidate.profile.login": canonical_login or candidate_login,
        "candidate.profile.account_age_days": account_age_days,
        "candidate.profile.login_features": sorted(login_features),
        "candidate.profile.login_features.has_bot_suffix": candidate_login.lower().endswith("[bot]"),
        # E2 activity
        "candidate.activity.last_seen_seconds": None
        if days_since is None
        else float(days_since) * 86400.0,
        "candidate.activity.review_count_180d": review_count_180d,
        "candidate.activity.comment_count_180d": comment_count_180d,
        "candidate.activity.authored_pr_count_180d": authored_pr_180d,
        "candidate.activity.unique_areas_touched_180d": len(set(areas)),
        "candidate.activity.entropy_over_areas_180d": normalized_entropy(area_counts.values()),
        "candidate.activity.load_proxy.open_reviews_est": open_reviews_est,
        # E3 footprint (top-N sparse maps)
        "candidate.footprint.area_scores.topN": _top_n_scores(area_counts, top_n=footprint_top_n),
        "candidate.footprint.dir_depth3_scores.topN": _top_n_scores(dir_counts, top_n=footprint_top_n),
        "candidate.footprint.path_scores.topN": _top_n_scores(path_counts, top_n=footprint_top_n),
    }

    for days in sorted(counts):
        out[f"candidate.activity.event_counts_{days}d"] = int(counts[days])

    # Backward-compat aliases.
    out["cand.activity.days_since_last_event"] = days_since
    out["cand.activity.has_prior_event"] = days_since is not None
    for days in sorted(counts):
        out[f"cand.activity.events_{days}d"] = int(counts[days])

    return {k: out[k] for k in sorted(out)}


def build_candidate_activity_table(
    *,
    input: PRInputBundle,
    candidate_logins: list[str],
    data_dir: str | Path,
    windows_days: tuple[int, ...] = (7, 30, 90, 180),
    footprint_top_n: int = 12,
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for login in sorted(set(candidate_logins), key=lambda s: s.lower()):
        out[login] = build_candidate_activity_features(
            input=input,
            candidate_login=login,
            data_dir=data_dir,
            windows_days=windows_days,
            footprint_top_n=footprint_top_n,
        )
    return {k: out[k] for k in sorted(out, key=str.lower)}
