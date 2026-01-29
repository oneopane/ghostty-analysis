from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from repo_routing.paths import repo_db_path


def _parse_dt(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def _dt_sql(dt: datetime) -> str:
    return dt.replace(tzinfo=None).isoformat(sep=" ")


def _is_bot_login(login: str) -> bool:
    # Best-effort; canonical bot detection uses users.type when available.
    return login.lower().endswith("[bot]")


def behavior_truth_first_eligible_review(
    *,
    repo: str,
    pr_number: int,
    cutoff: datetime,
    data_dir: str | Path = "data",
    exclude_author: bool = True,
    exclude_bots: bool = True,
) -> str | None:
    """v0 behavior truth: first non-author/non-bot review (by submitted_at)."""

    db = repo_db_path(repo_full_name=repo, data_dir=data_dir)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "select id from repos where full_name = ?", (repo,)
        ).fetchone()
        if row is None:
            raise KeyError(f"repo not found in db: {repo}")
        repo_id = int(row["id"])

        pr = conn.execute(
            "select id, user_id from pull_requests where repo_id = ? and number = ?",
            (repo_id, pr_number),
        ).fetchone()
        if pr is None:
            raise KeyError(f"pr not found: {repo}#{pr_number}")

        pr_id = int(pr["id"])
        author_id = pr["user_id"]

        cutoff_s = _dt_sql(cutoff)
        rows = conn.execute(
            """
            select r.user_id as user_id, u.login as login, u.type as type, r.submitted_at as submitted_at
            from reviews r
            join users u on u.id = r.user_id
            where r.repo_id = ?
              and r.pull_request_id = ?
              and r.submitted_at is not null
              and r.submitted_at <= ?
              and u.login is not null
            order by r.submitted_at asc, r.id asc
            """,
            (repo_id, pr_id, cutoff_s),
        ).fetchall()

        for r in rows:
            if exclude_bots and (r["type"] == "Bot" or _is_bot_login(str(r["login"]))):
                continue
            if exclude_author and author_id is not None and r["user_id"] == author_id:
                continue
            return str(r["login"])
        return None
    finally:
        conn.close()


def intent_truth_from_review_requests(
    *,
    repo: str,
    pr_number: int,
    cutoff: datetime,
    window: timedelta = timedelta(minutes=60),
    data_dir: str | Path = "data",
) -> list[str]:
    """v0 intent truth: review requests active at cutoff within a fixed window.

    This reads from the PR review_request interval table (as-of safety).
    """

    # For v0, we interpret the rule as: look at review requests active at cutoff
    # and include them if the review-request interval started within [cutoff-window, cutoff].
    start = cutoff - window

    db = repo_db_path(repo_full_name=repo, data_dir=data_dir)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        pr_row = conn.execute(
            """
            select pr.id as pr_id
            from pull_requests pr
            join repos r on r.id = pr.repo_id
            where r.full_name = ? and pr.number = ?
            """,
            (repo, pr_number),
        ).fetchone()
        if pr_row is None:
            raise KeyError(f"pr not found: {repo}#{pr_number}")

        pr_id = int(pr_row["pr_id"])

        cutoff_s = _dt_sql(cutoff)
        start_s = _dt_sql(start)
        rows = conn.execute(
            """
            select rri.reviewer_type as reviewer_type,
                   rri.reviewer_id as reviewer_id,
                   se.occurred_at as start_at
            from pull_request_review_request_intervals rri
            join events se on se.id = rri.start_event_id
            left join events ee on ee.id = rri.end_event_id
            where rri.pull_request_id = ?
              and se.occurred_at <= ?
              and (ee.id is null or ? < ee.occurred_at)
              and se.occurred_at >= ?
            order by rri.reviewer_type asc, rri.reviewer_id asc
            """,
            (pr_id, cutoff_s, cutoff_s, start_s),
        ).fetchall()

        out: list[str] = []
        for rr in rows:
            if rr["reviewer_type"] == "Team":
                team = conn.execute(
                    "select slug from teams where id = ?", (int(rr["reviewer_id"]),)
                ).fetchone()
                if team is None or team["slug"] is None:
                    continue
                out.append(f"team:{team['slug']}")
            else:
                user = conn.execute(
                    "select login, type from users where id = ?",
                    (int(rr["reviewer_id"]),),
                ).fetchone()
                if user is None or user["login"] is None:
                    continue
                if user["type"] == "Bot":
                    continue
                out.append(f"user:{user['login']}")

        # stable, deterministic
        return sorted(set(out), key=lambda s: s.lower())
    finally:
        conn.close()
