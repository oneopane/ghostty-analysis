from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from repo_routing.boundary.models import MembershipMode
from repo_routing.boundary.pipeline import write_boundary_model_artifacts
from repo_routing.paths import repo_db_path
from repo_routing.router.stewards import StewardsRouter


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

        conn.execute("insert into repos (id, full_name) values (1, ?)", (repo,))
        conn.execute("insert into users (id, login, type) values (1, 'alice', null)")
        conn.execute("insert into users (id, login, type) values (2, 'bob', null)")
        conn.execute("insert into users (id, login, type) values (3, 'carol', null)")

        conn.execute(
            """
            insert into pull_requests
            (id, repo_id, number, issue_id, user_id, created_at, title, body, base_sha, base_ref)
            values
            (101, 1, 1, null, 1, '2024-01-10 00:00:00', 'Add feature',
             'Issue: #123
AI: no
Provenance: human', 'base1', 'main'),
            (102, 1, 2, null, 1, '2024-01-05 00:00:00', 'Refactor',
             'Issue: #124
AI: no
Provenance: human', 'base2', 'main'),
            (103, 1, 3, null, 1, '2024-01-05 00:00:00', 'Docs',
             'Issue: #125
AI: no
Provenance: human', 'base3', 'main')
            """
        )

        conn.execute(
            "insert into events (id, occurred_at) values (1, '2024-01-01 00:00:00')"
        )
        conn.execute(
            "insert into events (id, occurred_at) values (2, '2024-01-01 00:00:00')"
        )
        conn.execute(
            "insert into events (id, occurred_at) values (3, '2024-01-01 00:00:00')"
        )

        conn.execute(
            """
            insert into pull_request_head_intervals
            (id, pull_request_id, head_sha, head_ref, start_event_id, end_event_id)
            values
            (1, 101, 'head1', 'main', 1, null),
            (2, 102, 'head2', 'main', 2, null),
            (3, 103, 'head3', 'main', 3, null)
            """
        )

        conn.execute(
            """
            insert into pull_request_files
            (repo_id, pull_request_id, head_sha, path, status, additions, deletions, changes)
            values
            (1, 101, 'head1', 'src/app.py', 'modified', 10, 2, 12),
            (1, 102, 'head2', 'src/util.py', 'modified', 3, 1, 4),
            (1, 103, 'head3', 'docs/guide.md', 'modified', 1, 0, 1)
            """
        )

        conn.execute(
            """
            insert into reviews
            (id, repo_id, pull_request_id, user_id, state, submitted_at)
            values
            (201, 1, 102, 2, 'APPROVED', '2024-01-05 12:00:00')
            """
        )

        conn.execute(
            """
            insert into comments
            (id, repo_id, pull_request_id, user_id, created_at, path, comment_type, review_id)
            values
            (301, 1, 103, 3, '2024-01-05 12:00:00', null, 'issue', null)
            """
        )

        conn.commit()
    finally:
        conn.close()

    return base_dir


def test_stewards_router_ranks_candidates(tmp_path: Path) -> None:
    data_dir = _seed_db(tmp_path / "data")
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "version": "v0",
                "feature_version": "v0",
                "candidate_pool": {
                    "lookback_days": 180,
                    "exclude_author": True,
                    "exclude_bots": True,
                },
                "decay": {"half_life_days": 30, "lookback_days": 180},
                "event_weights": {
                    "review_submitted": 1.0,
                    "review_comment_created": 0.4,
                    "comment_created": 0.2,
                },
                "weights": {"boundary_overlap_activity": 1.0, "activity_total": 0.2},
                "filters": {"min_activity_total": 0.0},
                "thresholds": {"confidence_high_margin": 0.1, "confidence_med_margin": 0.05},
                "labels": {"include_boundary_labels": False},
            }
        ),
        encoding="utf-8",
    )

    write_boundary_model_artifacts(
        repo_full_name="acme/widgets",
        cutoff_utc=datetime(2024, 1, 10, tzinfo=timezone.utc),
        cutoff_key="2024-01-10T00-00-00Z",
        data_dir=data_dir,
        membership_mode=MembershipMode.MIXED,
    )

    router = StewardsRouter(config_path=config_path)
    result = router.route(
        repo="acme/widgets",
        pr_number=1,
        as_of=datetime(2024, 1, 10, tzinfo=timezone.utc),
        data_dir=data_dir,
        top_k=2,
    )

    assert result.candidates[0].target.name == "bob"
    assert result.confidence == "high"
    assert result.risk == "medium"
