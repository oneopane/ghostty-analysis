from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from repo_routing.exports.extract import (
    PRCutoff,
    export_pr_activity_rows,
    export_pr_files_rows,
    export_pr_snapshots,
    export_pr_text_rows,
    export_prs_rows,
    export_truth_behavior_rows,
    export_truth_intent_rows,
)
from repo_routing.paths import repo_db_path


def _seed_db(base_dir: Path) -> Path:
    repo = "acme/widgets"
    db_path = repo_db_path(repo_full_name=repo, data_dir=base_dir)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "create table repos (id integer primary key, full_name text not null)"
        )
        conn.execute(
            "create table users (id integer primary key, login text, type text)"
        )
        conn.execute(
            "create table teams (id integer primary key, slug text)"
        )
        conn.execute(
            """
            create table pull_requests (
                id integer primary key,
                repo_id integer,
                number integer,
                issue_id integer,
                user_id integer,
                created_at text,
                title text,
                body text,
                base_sha text,
                base_ref text
            )
            """
        )
        conn.execute(
            "create table events (id integer primary key, occurred_at text)"
        )
        conn.execute(
            """
            create table pull_request_head_intervals (
                id integer primary key,
                pull_request_id integer,
                head_sha text,
                head_ref text,
                start_event_id integer,
                end_event_id integer
            )
            """
        )
        conn.execute(
            """
            create table pull_request_files (
                repo_id integer,
                pull_request_id integer,
                head_sha text,
                path text,
                status text,
                additions integer,
                deletions integer,
                changes integer
            )
            """
        )
        conn.execute(
            """
            create table pull_request_review_request_intervals (
                id integer primary key,
                pull_request_id integer,
                reviewer_type text,
                reviewer_id integer,
                start_event_id integer,
                end_event_id integer
            )
            """
        )
        conn.execute(
            """
            create table reviews (
                id integer primary key,
                repo_id integer,
                pull_request_id integer,
                user_id integer,
                state text,
                submitted_at text
            )
            """
        )
        conn.execute(
            """
            create table comments (
                id integer primary key,
                repo_id integer,
                pull_request_id integer,
                user_id integer,
                created_at text,
                path text,
                comment_type text,
                review_id integer
            )
            """
        )

        conn.execute("insert into repos (id, full_name) values (1, ?)", (repo,))
        conn.execute("insert into users (id, login, type) values (1, 'alice', null)")
        conn.execute("insert into users (id, login, type) values (2, 'bob', null)")
        conn.execute("insert into users (id, login, type) values (3, 'ci[bot]', 'Bot')")
        conn.execute("insert into teams (id, slug) values (10, 'platform')")

        conn.execute(
            """
            insert into pull_requests
            (id, repo_id, number, issue_id, user_id, created_at, title, body, base_sha, base_ref)
            values
            (101, 1, 1, null, 1, '2024-01-01 00:00:00', 'Add feature',
             'Issue: #123\\nAI: no\\nProvenance: human', 'base1', 'main'),
            (102, 1, 2, null, 1, '2024-01-02 00:00:00', 'Fix bug',
             'No issue', 'base2', 'main')
            """
        )

        conn.execute(
            "insert into events (id, occurred_at) values (1, '2024-01-01 00:00:00')"
        )
        conn.execute(
            "insert into events (id, occurred_at) values (2, '2024-01-02 00:00:00')"
        )
        conn.execute(
            "insert into events (id, occurred_at) values (3, '2024-01-01 00:30:00')"
        )

        conn.execute(
            """
            insert into pull_request_head_intervals
            (id, pull_request_id, head_sha, head_ref, start_event_id, end_event_id)
            values
            (1, 101, 'head1', 'main', 1, null),
            (2, 102, 'head2', 'main', 2, null)
            """
        )

        conn.execute(
            """
            insert into pull_request_files
            (repo_id, pull_request_id, head_sha, path, status, additions, deletions, changes)
            values
            (1, 101, 'head1', 'src/app.py', 'modified', 10, 2, 12),
            (1, 102, 'head2', 'README.md', 'modified', 1, 0, 1)
            """
        )

        conn.execute(
            """
            insert into reviews
            (id, repo_id, pull_request_id, user_id, state, submitted_at)
            values
            (201, 1, 101, 3, 'APPROVED', '2024-01-02 00:00:00'),
            (202, 1, 101, 2, 'APPROVED', '2024-01-03 00:00:00')
            """
        )

        conn.execute(
            """
            insert into comments
            (id, repo_id, pull_request_id, user_id, created_at, path, comment_type, review_id)
            values
            (301, 1, 101, 2, '2024-01-01 12:00:00', null, 'issue', null),
            (302, 1, 101, 2, '2024-01-01 13:00:00', 'src/app.py', 'review', 201)
            """
        )

        conn.execute(
            """
            insert into pull_request_review_request_intervals
            (id, pull_request_id, reviewer_type, reviewer_id, start_event_id, end_event_id)
            values
            (401, 101, 'User', 2, 3, null)
            """
        )
        conn.commit()
    finally:
        conn.close()

    return base_dir


def test_export_deterministic_order(tmp_path: Path) -> None:
    data_dir = _seed_db(tmp_path / "data")
    repo = "acme/widgets"

    cutoffs = [
        PRCutoff(
            pr_number=2,
            cutoff=datetime(2024, 1, 2, tzinfo=timezone.utc),
            cutoff_policy="created_at",
        ),
        PRCutoff(
            pr_number=1,
            cutoff=datetime(2024, 1, 1, tzinfo=timezone.utc),
            cutoff_policy="created_at",
        ),
    ]

    snaps = export_pr_snapshots(repo=repo, data_dir=data_dir, pr_cutoffs=cutoffs)
    rows = export_prs_rows(snaps)
    assert [r["pr_number"] for r in rows] == [1, 2]

    text_rows = export_pr_text_rows(snaps)
    assert [r["pr_number"] for r in text_rows] == [1, 2]

    file_rows = export_pr_files_rows(snaps)
    assert [r["path"] for r in file_rows] == ["src/app.py", "README.md"]
    assert [r["default_boundary"] for r in file_rows] == ["src", "__root__"]


def test_export_activity_and_truth(tmp_path: Path) -> None:
    data_dir = _seed_db(tmp_path / "data")
    repo = "acme/widgets"

    activity = export_pr_activity_rows(
        repo=repo,
        data_dir=data_dir,
        start_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_at=datetime(2024, 1, 4, tzinfo=timezone.utc),
    )
    kinds = [row["kind"] for row in activity]
    assert kinds == [
        "comment_created",
        "review_comment_created",
        "review_submitted",
        "review_submitted",
    ]

    cutoffs = [
        PRCutoff(
            pr_number=1,
            cutoff=datetime(2024, 1, 1, tzinfo=timezone.utc),
            cutoff_policy="created_at",
        ),
        PRCutoff(
            pr_number=2,
            cutoff=datetime(2024, 1, 2, tzinfo=timezone.utc),
            cutoff_policy="created_at",
        ),
    ]

    behavior = export_truth_behavior_rows(
        repo=repo,
        data_dir=data_dir,
        pr_cutoffs=cutoffs,
    )
    assert behavior[0]["truth_behavior_first_reviewer"] == "bob"
    assert behavior[1]["truth_behavior_first_reviewer"] is None

    intent = export_truth_intent_rows(
        repo=repo,
        data_dir=data_dir,
        pr_cutoffs=cutoffs,
    )
    assert intent[0]["target_type"] == "user"
    assert intent[0]["target_name"] == "bob"
