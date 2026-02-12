from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pytest

from repo_routing.boundary.hash import boundary_model_hash
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
            "insert into pull_requests (id, repo_id, number, created_at) values (102, 1, 2, '2024-01-11 00:00:00')"
        )
        conn.execute(
            "insert into pull_requests (id, repo_id, number, created_at) values (103, 1, 3, '2024-02-01 00:00:00')"
        )

        rows = [
            (1, 101, "h1", "src/a.py"),
            (1, 101, "h1", "src/b.py"),
            (1, 102, "h2", "src/a.py"),
            (1, 102, "h2", "tests/test_a.py"),
            (1, 103, "h3", "docs/readme.md"),
        ]
        for repo_id, pr_id, head_sha, path in rows:
            conn.execute(
                """
                insert into pull_request_files
                (repo_id, pull_request_id, head_sha, path, status, additions, deletions, changes)
                values (?, ?, ?, ?, 'modified', 1, 1, 2)
                """,
                (repo_id, pr_id, head_sha, path),
            )

        conn.commit()
    finally:
        conn.close()

    return repo


def test_hybrid_v1_inference_is_deterministic(tmp_path: Path) -> None:
    repo = _seed_boundary_db(tmp_path)
    cutoff = datetime(2024, 1, 20, tzinfo=timezone.utc)

    model_a, _ = build_boundary_model(
        repo_full_name=repo,
        cutoff_utc=cutoff,
        data_dir=tmp_path,
        membership_mode=MembershipMode.MIXED,
    )
    model_b, _ = build_boundary_model(
        repo_full_name=repo,
        cutoff_utc=cutoff,
        data_dir=tmp_path,
        membership_mode=MembershipMode.MIXED,
    )

    assert boundary_model_hash(model_a) == boundary_model_hash(model_b)
    assert [u.path for u in model_a.units] == ["src/a.py", "src/b.py", "tests/test_a.py"]
    assert {b.boundary_id for b in model_a.boundaries} == {"dir:src", "dir:tests"}

    sums = defaultdict(float)
    for m in model_a.memberships:
        sums[m.unit_id] += m.weight
    for total in sums.values():
        assert total == pytest.approx(1.0, abs=1e-6)


def test_hybrid_v1_hard_mode_has_single_membership_per_file(tmp_path: Path) -> None:
    repo = _seed_boundary_db(tmp_path)
    cutoff = datetime(2024, 1, 20, tzinfo=timezone.utc)

    model, _ = build_boundary_model(
        repo_full_name=repo,
        cutoff_utc=cutoff,
        data_dir=tmp_path,
        membership_mode=MembershipMode.HARD,
    )

    by_unit = defaultdict(list)
    for m in model.memberships:
        by_unit[m.unit_id].append(m)

    assert all(len(ms) == 1 for ms in by_unit.values())
    assert all(ms[0].weight == pytest.approx(1.0) for ms in by_unit.values())
