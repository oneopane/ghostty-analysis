from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from ...paths import repo_db_path
from ...time import dt_sql_utc, parse_dt_utc


@dataclass(frozen=True)
class RepoPrIds:
    repo_id: int
    pull_request_id: int
    issue_id: int | None
    author_id: int | None


def connect_repo_db(*, repo: str, data_dir: str | Path) -> sqlite3.Connection:
    """Open repo DB with row factory configured.

    Callers must close the returned connection.
    """
    conn = sqlite3.connect(str(repo_db_path(repo_full_name=repo, data_dir=data_dir)))
    conn.row_factory = sqlite3.Row
    return conn


def load_repo_pr_ids(
    *,
    conn: sqlite3.Connection,
    repo: str,
    pr_number: int,
) -> RepoPrIds:
    row = conn.execute(
        "select id from repos where full_name = ?",
        (repo,),
    ).fetchone()
    if row is None:
        raise KeyError(f"repo not found in db: {repo}")
    repo_id = int(row["id"])

    pr = conn.execute(
        """
        select id, issue_id, user_id
        from pull_requests
        where repo_id = ? and number = ?
        """,
        (repo_id, pr_number),
    ).fetchone()
    if pr is None:
        raise KeyError(f"pr not found: {repo}#{pr_number}")

    return RepoPrIds(
        repo_id=repo_id,
        pull_request_id=int(pr["id"]),
        issue_id=(int(pr["issue_id"]) if pr["issue_id"] is not None else None),
        author_id=(int(pr["user_id"]) if pr["user_id"] is not None else None),
    )


def cutoff_sql(cutoff: datetime) -> str:
    """Format UTC cutoff as SQL timestamp for <= / >= predicates."""
    return dt_sql_utc(cutoff, timespec="microseconds")


def count_head_updates_pre_cutoff(
    *,
    conn: sqlite3.Connection,
    pull_request_id: int,
    cutoff: datetime,
) -> int:
    row = conn.execute(
        """
        select count(*) as n
        from pull_request_head_intervals phi
        join events se on se.id = phi.start_event_id
        where phi.pull_request_id = ?
          and se.occurred_at <= ?
        """,
        (pull_request_id, cutoff_sql(cutoff)),
    ).fetchone()
    return 0 if row is None else int(row["n"])


def is_draft_at_cutoff(
    *,
    conn: sqlite3.Connection,
    pull_request_id: int,
    cutoff: datetime,
) -> bool:
    cutoff_s = cutoff_sql(cutoff)
    row = conn.execute(
        """
        select di.is_draft as is_draft
        from pull_request_draft_intervals di
        join events se on se.id = di.start_event_id
        left join events ee on ee.id = di.end_event_id
        where di.pull_request_id = ?
          and se.occurred_at <= ?
          and (ee.id is null or ? < ee.occurred_at)
        order by se.occurred_at desc, se.id desc
        limit 1
        """,
        (pull_request_id, cutoff_s, cutoff_s),
    ).fetchone()
    if row is None:
        return False
    return bool(row["is_draft"])


def active_review_request_counts(
    *,
    conn: sqlite3.Connection,
    pull_request_id: int,
    cutoff: datetime,
) -> tuple[int, int]:
    cutoff_s = cutoff_sql(cutoff)
    row = conn.execute(
        """
        select
          sum(case when rri.reviewer_type = 'User' then 1 else 0 end) as users_n,
          sum(case when rri.reviewer_type = 'Team' then 1 else 0 end) as teams_n
        from pull_request_review_request_intervals rri
        join events se on se.id = rri.start_event_id
        left join events ee on ee.id = rri.end_event_id
        where rri.pull_request_id = ?
          and se.occurred_at <= ?
          and (ee.id is null or ? < ee.occurred_at)
        """,
        (pull_request_id, cutoff_s, cutoff_s),
    ).fetchone()
    if row is None:
        return 0, 0
    users_n = int(row["users_n"] or 0)
    teams_n = int(row["teams_n"] or 0)
    return users_n, teams_n


def latest_author_activity_pre_cutoff(
    *,
    conn: sqlite3.Connection,
    repo_id: int,
    pull_request_id: int,
    author_id: int | None,
    cutoff: datetime,
) -> datetime | None:
    if author_id is None:
        return None

    row = conn.execute(
        """
        select max(ts) as latest_ts
        from (
          select c.created_at as ts
          from comments c
          where c.repo_id = ?
            and c.pull_request_id = ?
            and c.user_id = ?
            and c.created_at is not null
            and c.created_at <= ?

          union all

          select r.submitted_at as ts
          from reviews r
          where r.repo_id = ?
            and r.pull_request_id = ?
            and r.user_id = ?
            and r.submitted_at is not null
            and r.submitted_at <= ?

          union all

          select e.occurred_at as ts
          from events e
          where e.repo_id = ?
            and e.actor_id = ?
            and e.subject_type = 'pull_request'
            and e.subject_id = ?
            and e.occurred_at <= ?
        )
        """,
        (
            repo_id,
            pull_request_id,
            author_id,
            cutoff_sql(cutoff),
            repo_id,
            pull_request_id,
            author_id,
            cutoff_sql(cutoff),
            repo_id,
            author_id,
            pull_request_id,
            cutoff_sql(cutoff),
        ),
    ).fetchone()

    if row is None or row["latest_ts"] is None:
        return None
    return parse_dt_utc(row["latest_ts"])


def comment_counts_pre_cutoff(
    *,
    conn: sqlite3.Connection,
    repo_id: int,
    pull_request_id: int,
    author_id: int | None,
    cutoff: datetime,
) -> tuple[int, int]:
    row = conn.execute(
        """
        select
          sum(case when (? is not null and c.user_id = ?) then 1 else 0 end) as author_n,
          sum(case when (? is null or c.user_id != ?) then 1 else 0 end) as non_author_n
        from comments c
        where c.repo_id = ?
          and c.pull_request_id = ?
          and c.created_at is not null
          and c.created_at <= ?
        """,
        (
            author_id,
            author_id,
            author_id,
            author_id,
            repo_id,
            pull_request_id,
            cutoff_sql(cutoff),
        ),
    ).fetchone()
    if row is None:
        return 0, 0
    return int(row["author_n"] or 0), int(row["non_author_n"] or 0)


def review_count_pre_cutoff(
    *,
    conn: sqlite3.Connection,
    repo_id: int,
    pull_request_id: int,
    cutoff: datetime,
) -> int:
    row = conn.execute(
        """
        select count(*) as n
        from reviews r
        where r.repo_id = ?
          and r.pull_request_id = ?
          and r.submitted_at is not null
          and r.submitted_at <= ?
        """,
        (repo_id, pull_request_id, cutoff_sql(cutoff)),
    ).fetchone()
    return 0 if row is None else int(row["n"])


def candidate_last_activity_and_counts(
    *,
    conn: sqlite3.Connection,
    repo_id: int,
    candidate_login: str,
    cutoff: datetime,
    windows_days: tuple[int, ...],
) -> tuple[datetime | None, dict[int, int]]:
    user = conn.execute(
        "select id from users where lower(login) = lower(?) limit 1",
        (candidate_login,),
    ).fetchone()
    if user is None:
        return None, {int(d): 0 for d in windows_days}

    user_id = int(user["id"])
    cutoff_s = cutoff_sql(cutoff)

    last_row = conn.execute(
        """
        select max(ts) as latest_ts
        from (
          select r.submitted_at as ts
          from reviews r
          where r.repo_id = ?
            and r.user_id = ?
            and r.submitted_at is not null
            and r.submitted_at <= ?

          union all

          select c.created_at as ts
          from comments c
          where c.repo_id = ?
            and c.user_id = ?
            and c.created_at is not null
            and c.created_at <= ?
        )
        """,
        (repo_id, user_id, cutoff_s, repo_id, user_id, cutoff_s),
    ).fetchone()

    latest_ts = (
        None
        if last_row is None or last_row["latest_ts"] is None
        else parse_dt_utc(last_row["latest_ts"])
    )

    out: dict[int, int] = {}
    for days in windows_days:
        window_start = cutoff - timedelta(days=int(days))
        row = conn.execute(
            """
            select count(*) as n
            from (
              select r.id as id
              from reviews r
              where r.repo_id = ?
                and r.user_id = ?
                and r.submitted_at is not null
                and r.submitted_at >= ?
                and r.submitted_at <= ?

              union all

              select c.id as id
              from comments c
              where c.repo_id = ?
                and c.user_id = ?
                and c.created_at is not null
                and c.created_at >= ?
                and c.created_at <= ?
            )
            """,
            (
                repo_id,
                user_id,
                cutoff_sql(window_start),
                cutoff_s,
                repo_id,
                user_id,
                cutoff_sql(window_start),
                cutoff_s,
            ),
        ).fetchone()
        out[int(days)] = 0 if row is None else int(row["n"])

    return latest_ts, out
