from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ...paths import repo_db_path
from ...time import dt_sql_utc


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
    """Resolve stable IDs for repo + PR number.

    High-level SQL:
    - repos.full_name -> repos.id
    - pull_requests by (repo_id, number)
    """
    raise NotImplementedError("TODO: implement repo/pr id resolver")


def cutoff_sql(cutoff: datetime) -> str:
    """Format UTC cutoff as SQL timestamp for <= / >= predicates."""
    return dt_sql_utc(cutoff, timespec="microseconds")


def count_head_updates_pre_cutoff(
    *,
    conn: sqlite3.Connection,
    pull_request_id: int,
    cutoff: datetime,
) -> int:
    """TODO feature #29: number of head updates before cutoff.

    High-level SQL source:
    - pull_request_head_intervals joined to start events
    - count rows with start_event.occurred_at <= cutoff
    """
    raise NotImplementedError("TODO: implement head update count query")


def is_draft_at_cutoff(
    *,
    conn: sqlite3.Connection,
    pull_request_id: int,
    cutoff: datetime,
) -> bool:
    """TODO feature #26: PR draft state as-of cutoff.

    High-level SQL source:
    - pull_request_draft_intervals active at cutoff using interval predicate
    """
    raise NotImplementedError("TODO: implement draft-at-cutoff query")


def active_review_request_counts(
    *,
    conn: sqlite3.Connection,
    pull_request_id: int,
    cutoff: datetime,
) -> tuple[int, int]:
    """TODO features #35/#36: active requested users/teams at cutoff.

    High-level SQL source:
    - pull_request_review_request_intervals active at cutoff
    - split by reviewer_type User vs Team
    """
    raise NotImplementedError("TODO: implement active review-request query")


def latest_author_activity_pre_cutoff(
    *,
    conn: sqlite3.Connection,
    repo_id: int,
    pull_request_id: int,
    author_id: int | None,
    cutoff: datetime,
) -> datetime | None:
    """TODO feature #30: last author activity timestamp pre-cutoff.

    High-level SQL source:
    - max timestamp across comments/reviews/events by author for this PR/repo <= cutoff
    """
    raise NotImplementedError("TODO: implement latest author activity query")


def comment_counts_pre_cutoff(
    *,
    conn: sqlite3.Connection,
    repo_id: int,
    pull_request_id: int,
    author_id: int | None,
    cutoff: datetime,
) -> tuple[int, int]:
    """TODO features #31/#32: author and non-author comment counts.

    High-level SQL source:
    - comments table filtered by repo_id + pull_request_id + created_at <= cutoff
    - split on user_id == author_id vs != author_id
    """
    raise NotImplementedError("TODO: implement comment count query")


def review_count_pre_cutoff(
    *,
    conn: sqlite3.Connection,
    repo_id: int,
    pull_request_id: int,
    cutoff: datetime,
) -> int:
    """TODO feature #33: number of submitted reviews pre-cutoff.

    High-level SQL source:
    - reviews table with submitted_at <= cutoff
    """
    raise NotImplementedError("TODO: implement review count query")


def candidate_last_activity_and_counts(
    *,
    conn: sqlite3.Connection,
    repo_id: int,
    candidate_login: str,
    cutoff: datetime,
    windows_days: tuple[int, ...],
) -> tuple[datetime | None, dict[int, int]]:
    """TODO features #49/#50 for candidate activity.

    High-level SQL source:
    - resolve users.id by login
    - union reviews + comments events in repo <= cutoff
    - compute max timestamp (recency)
    - compute windowed counts for 30/90/180d (or configured windows)
    """
    raise NotImplementedError("TODO: implement candidate activity queries")
