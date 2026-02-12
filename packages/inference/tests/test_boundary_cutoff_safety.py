from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from repo_routing.boundary.models import MembershipMode
from repo_routing.boundary.pipeline import build_boundary_model


def _seed_boundary_db(base_dir: Path) -> str:
    repo = "acme/widgets"
    owner, name = repo.split("/", 1)
    db_path = base_dir / "github" / owner / name / "history.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("create table repos (id integer primary key, full_name text not null)")
        conn.execute(
            """
            create table pull_requests (
                id integer primary key,
                repo_id integer,
                number integer,
                created_at text
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

        conn.execute("insert into repos (id, full_name) values (1, ?)", (repo,))
        conn.execute(
            "insert into pull_requests (id, repo_id, number, created_at) values (101, 1, 1, '2024-01-10 00:00:00')"
        )
        conn.execute(
            "insert into pull_requests (id, repo_id, number, created_at) values (102, 1, 2, '2024-02-01 00:00:00')"
        )

        conn.execute(
            """
            insert into pull_request_files
            (repo_id, pull_request_id, head_sha, path, status, additions, deletions, changes)
            values
            (1, 101, 'h1', 'src/a.py', 'modified', 1, 1, 2),
            (1, 102, 'h2', 'docs/readme.md', 'modified', 1, 1, 2)
            """
        )
        conn.commit()
    finally:
        conn.close()

    return repo


def test_post_cutoff_pr_does_not_affect_output(tmp_path: Path) -> None:
    repo = _seed_boundary_db(tmp_path)

    early_model, _ = build_boundary_model(
        repo_full_name=repo,
        cutoff_utc=datetime(2024, 1, 15, tzinfo=timezone.utc),
        data_dir=tmp_path,
        membership_mode=MembershipMode.MIXED,
    )
    late_model, _ = build_boundary_model(
        repo_full_name=repo,
        cutoff_utc=datetime(2024, 2, 15, tzinfo=timezone.utc),
        data_dir=tmp_path,
        membership_mode=MembershipMode.MIXED,
    )

    early_files = {u.path for u in early_model.units}
    late_files = {u.path for u in late_model.units}

    assert early_files == {"src/a.py"}
    assert late_files == {"src/a.py", "docs/readme.md"}
