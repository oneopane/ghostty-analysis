from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class MinDb:
    data_dir: Path
    repo: str
    db_path: Path
    pr_number: int
    author_login: str
    reviewer_login: str
    created_at: datetime


def build_min_db(
    *,
    tmp_path: Path,
    repo: str = "acme/widgets",
    pr_number: int = 1,
    created_at: datetime | None = None,
    draft_at_open: bool = False,
    ready_for_review_at: datetime | None = None,
) -> MinDb:
    owner, name = repo.split("/", 1)
    data_dir = tmp_path / "data"
    db_path = data_dir / "github" / owner / name / "history.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    created_at = created_at or datetime.fromisoformat("2024-01-01T00:00:00+00:00")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        c = conn.cursor()

        c.execute("create table repos (id integer primary key, full_name text)")
        c.execute("create table users (id integer primary key, login text, type text)")
        c.execute(
            "create table pull_requests (id integer primary key, repo_id integer, issue_id integer, number integer, user_id integer, created_at text, title text, body text, base_sha text, base_ref text)"
        )
        c.execute(
            "create table events (id integer primary key, repo_id integer, occurred_at text, actor_id integer, subject_type text, subject_id integer, event_type text, object_type text, object_id integer, commit_sha text, payload_json text, event_key text)"
        )
        c.execute(
            "create table pull_request_head_intervals (id integer primary key, pull_request_id integer, head_sha text, head_ref text, start_event_id integer, end_event_id integer)"
        )
        c.execute(
            "create table pull_request_draft_intervals (id integer primary key, pull_request_id integer, is_draft integer, start_event_id integer, end_event_id integer)"
        )
        c.execute(
            "create table pull_request_files (id integer primary key, repo_id integer, pull_request_id integer, head_sha text, path text, status text, additions integer, deletions integer, changes integer)"
        )
        c.execute(
            "create table reviews (id integer primary key, repo_id integer, pull_request_id integer, user_id integer, submitted_at text)"
        )
        c.execute(
            "create table comments (id integer primary key, repo_id integer, pull_request_id integer, review_id integer, user_id integer, created_at text)"
        )
        c.execute(
            "create table pull_request_review_request_intervals (id integer primary key, pull_request_id integer, reviewer_type text, reviewer_id integer, start_event_id integer, end_event_id integer)"
        )
        c.execute("create table teams (id integer primary key, slug text)")

        c.execute("insert into repos (id, full_name) values (?, ?)", (1, repo))
        c.execute(
            "insert into users (id, login, type) values (?, ?, ?)",
            (10, "alice", "User"),
        )
        c.execute(
            "insert into users (id, login, type) values (?, ?, ?)", (11, "bob", "User")
        )

        c.execute(
            "insert into pull_requests (id, repo_id, issue_id, number, user_id, created_at, title, body, base_sha, base_ref) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                100,
                1,
                None,
                pr_number,
                10,
                created_at.replace(tzinfo=None).isoformat(sep=" "),
                "Test PR",
                "Please review @bob",
                "deadbeef" * 5,
                "main",
            ),
        )

        # Head interval + event so HistoryReader strict_as_of passes.
        c.execute(
            "insert into events (id, repo_id, occurred_at, actor_id, subject_type, subject_id, event_type, object_type, object_id, commit_sha, payload_json, event_key) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                200,
                1,
                created_at.replace(tzinfo=None).isoformat(sep=" "),
                10,
                "pull_request",
                100,
                "pull_request.synchronize",
                None,
                None,
                None,
                None,
                "e:head",
            ),
        )
        c.execute(
            "insert into pull_request_head_intervals (id, pull_request_id, head_sha, head_ref, start_event_id, end_event_id) values (?, ?, ?, ?, ?, ?)",
            (300, 100, "cafebabe" * 5, "main", 200, None),
        )

        # Draft intervals (used by cutoff policy).
        ready_for_review_at = ready_for_review_at or (
            created_at + timedelta(minutes=10)
        )
        ready_at = ready_for_review_at if draft_at_open else created_at

        # Initial draft state at creation.
        c.execute(
            "insert into events (id, repo_id, occurred_at, actor_id, subject_type, subject_id, event_type, object_type, object_id, commit_sha, payload_json, event_key) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                202,
                1,
                created_at.replace(tzinfo=None).isoformat(sep=" "),
                10,
                "pull_request",
                100,
                "pull_request.draft.set",
                None,
                None,
                None,
                '{"is_draft": %s}' % ("true" if draft_at_open else "false"),
                "e:draft0",
            ),
        )

        if draft_at_open:
            c.execute(
                "insert into events (id, repo_id, occurred_at, actor_id, subject_type, subject_id, event_type, object_type, object_id, commit_sha, payload_json, event_key) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    203,
                    1,
                    ready_at.replace(tzinfo=None).isoformat(sep=" "),
                    10,
                    "pull_request",
                    100,
                    "pull_request.draft.set",
                    None,
                    None,
                    None,
                    '{"is_draft": false}',
                    "e:draft1",
                ),
            )
            c.execute(
                "insert into pull_request_draft_intervals (id, pull_request_id, is_draft, start_event_id, end_event_id) values (?, ?, ?, ?, ?)",
                (310, 100, 1, 202, 203),
            )
            c.execute(
                "insert into pull_request_draft_intervals (id, pull_request_id, is_draft, start_event_id, end_event_id) values (?, ?, ?, ?, ?)",
                (311, 100, 0, 203, None),
            )
        else:
            c.execute(
                "insert into pull_request_draft_intervals (id, pull_request_id, is_draft, start_event_id, end_event_id) values (?, ?, ?, ?, ?)",
                (310, 100, 0, 202, None),
            )

        # One review request interval (active at cutoff).
        c.execute(
            "insert into events (id, repo_id, occurred_at, actor_id, subject_type, subject_id, event_type, object_type, object_id, commit_sha, payload_json, event_key) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                201,
                1,
                created_at.replace(tzinfo=None).isoformat(sep=" "),
                10,
                "pull_request",
                100,
                "pull_request.review_requested",
                "user",
                11,
                None,
                None,
                "e:rr",
            ),
        )
        c.execute(
            "insert into pull_request_review_request_intervals (id, pull_request_id, reviewer_type, reviewer_id, start_event_id, end_event_id) values (?, ?, ?, ?, ?, ?)",
            (400, 100, "User", 11, 201, None),
        )

        # One review and one comment after cutoff.
        c.execute(
            "insert into reviews (id, repo_id, pull_request_id, user_id, submitted_at) values (?, ?, ?, ?, ?)",
            (
                500,
                1,
                100,
                11,
                datetime.fromisoformat("2024-01-01T01:00:00+00:00")
                .replace(tzinfo=None)
                .isoformat(sep=" "),
            ),
        )
        c.execute(
            "insert into comments (id, repo_id, pull_request_id, review_id, user_id, created_at) values (?, ?, ?, ?, ?, ?)",
            (
                600,
                1,
                100,
                500,
                11,
                datetime.fromisoformat("2024-01-01T00:30:00+00:00")
                .replace(tzinfo=None)
                .isoformat(sep=" "),
            ),
        )

        conn.commit()
    finally:
        conn.close()

    return MinDb(
        data_dir=data_dir,
        repo=repo,
        db_path=db_path,
        pr_number=pr_number,
        author_login="alice",
        reviewer_login="bob",
        created_at=created_at,
    )
