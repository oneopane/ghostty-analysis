from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from repo_routing.mixed_membership.areas.basis import (
    build_user_area_activity_rows,
    rows_to_user_area_matrix,
)
from repo_routing.mixed_membership.config import AreaMembershipConfig
from repo_routing.mixed_membership.models.nmf import (
    build_candidate_role_mix_features,
    build_pair_role_affinity_features,
    fit_area_membership_nmf,
)


def _seed_db(tmp_path: Path) -> tuple[str, Path]:
    repo = "acme/widgets"
    owner, name = repo.split("/", 1)
    data_dir = tmp_path / "data"
    db = data_dir / "github" / owner / name / "history.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db))
    try:
        conn.execute("create table repos (id integer primary key, full_name text)")
        conn.execute("create table users (id integer primary key, login text, type text)")
        conn.execute(
            "create table pull_requests (id integer primary key, repo_id integer, number integer, user_id integer, created_at text)"
        )
        conn.execute(
            "create table reviews (id integer primary key, repo_id integer, pull_request_id integer, user_id integer, submitted_at text)"
        )
        conn.execute(
            "create table comments (id integer primary key, repo_id integer, pull_request_id integer, user_id integer, created_at text)"
        )
        conn.execute(
            "create table events (id integer primary key, occurred_at text, repo_id integer, actor_id integer, subject_type text, subject_id integer)"
        )
        conn.execute(
            "create table pull_request_head_intervals (id integer primary key, pull_request_id integer, start_event_id integer, end_event_id integer, head_sha text, head_ref text)"
        )
        conn.execute(
            "create table pull_request_files (id integer primary key, repo_id integer, pull_request_id integer, head_sha text, path text, changes integer)"
        )

        conn.execute("insert into repos (id, full_name) values (1, ?)", (repo,))
        conn.execute("insert into users (id, login, type) values (10, 'alice', 'User')")
        conn.execute("insert into users (id, login, type) values (11, 'bob', 'User')")
        conn.execute("insert into users (id, login, type) values (12, 'robot[bot]', 'Bot')")

        conn.execute(
            "insert into pull_requests (id, repo_id, number, user_id, created_at) values (100, 1, 1, 10, '2024-01-01 00:00:00')"
        )
        conn.execute(
            "insert into events (id, occurred_at, repo_id, actor_id, subject_type, subject_id) values (1, '2024-01-01 00:00:00', 1, 10, 'pull_request', 100)"
        )
        conn.execute(
            "insert into pull_request_head_intervals (id, pull_request_id, start_event_id, end_event_id, head_sha, head_ref) values (1, 100, 1, null, 'head1', 'main')"
        )
        conn.execute(
            "insert into pull_request_files (id, repo_id, pull_request_id, head_sha, path, changes) values (1, 1, 100, 'head1', 'src/app.py', 10)"
        )
        conn.execute(
            "insert into pull_request_files (id, repo_id, pull_request_id, head_sha, path, changes) values (2, 1, 100, 'head1', 'docs/readme.md', 2)"
        )

        conn.execute(
            "insert into reviews (id, repo_id, pull_request_id, user_id, submitted_at) values (1, 1, 100, 11, '2024-01-02 00:00:00')"
        )
        conn.execute(
            "insert into comments (id, repo_id, pull_request_id, user_id, created_at) values (1, 1, 100, 11, '2024-01-02 00:10:00')"
        )
        conn.execute(
            "insert into reviews (id, repo_id, pull_request_id, user_id, submitted_at) values (2, 1, 100, 12, '2024-01-02 00:20:00')"
        )

        conn.commit()
    finally:
        conn.close()

    return repo, data_dir


def test_build_user_area_activity_rows_and_matrix(tmp_path: Path) -> None:
    repo, data_dir = _seed_db(tmp_path)

    rows = build_user_area_activity_rows(
        repo=repo,
        cutoff=datetime(2024, 1, 3, tzinfo=timezone.utc),
        data_dir=data_dir,
        config=AreaMembershipConfig(lookback_days=30),
    )

    assert rows
    users = {r["user_login"] for r in rows}
    assert "bob" in users
    assert "robot[bot]" not in users

    matrix = rows_to_user_area_matrix(rows)
    assert matrix.users
    assert matrix.areas
    assert len(matrix.values) == len(matrix.users)
    assert len(matrix.values[0]) == len(matrix.areas)


def test_fit_nmf_and_derive_features(tmp_path: Path) -> None:
    pytest.importorskip("sklearn")
    pytest.importorskip("numpy")

    repo, data_dir = _seed_db(tmp_path)

    rows = build_user_area_activity_rows(
        repo=repo,
        cutoff=datetime(2024, 1, 3, tzinfo=timezone.utc),
        data_dir=data_dir,
        config=AreaMembershipConfig(lookback_days=30, n_components=2),
    )

    model = fit_area_membership_nmf(
        repo=repo,
        cutoff=datetime(2024, 1, 3, tzinfo=timezone.utc),
        rows=rows,
        config=AreaMembershipConfig(lookback_days=30, n_components=2),
    )

    assert model.roles
    assert model.model_hash

    cand = build_candidate_role_mix_features(model=model, candidate_logins=["bob", "carol"])
    assert "bob" in cand
    assert any(k.startswith("candidate.role_mix.k") for k in cand["bob"].keys())

    pair = build_pair_role_affinity_features(
        model=model,
        pr_area_distribution={"src": 0.8, "docs": 0.2},
        candidate_logins=["bob"],
    )
    assert "pair.affinity.pr_area_dot_candidate_role_mix" in pair["bob"]
