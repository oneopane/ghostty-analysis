from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from repo_routing.history.models import PullRequestSnapshot
from repo_routing.inputs.models import PRInputBundle
from repo_routing.predictor.features.candidate_activity import (
    build_candidate_activity_features,
    build_candidate_activity_table,
)
from repo_routing.predictor.features.sql import (
    candidate_last_activity_and_counts,
    connect_repo_db,
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
        conn.execute("create table users (id integer primary key, login text)")
        conn.execute(
            "create table pull_requests (id integer primary key, repo_id integer, number integer, issue_id integer, user_id integer)"
        )
        conn.execute(
            "create table reviews (id integer primary key, repo_id integer, user_id integer, pull_request_id integer, submitted_at text)"
        )
        conn.execute(
            "create table comments (id integer primary key, repo_id integer, user_id integer, pull_request_id integer, created_at text)"
        )

        conn.execute("insert into repos (id, full_name) values (1, ?)", (repo,))
        conn.execute("insert into users (id, login) values (10, 'alice')")
        conn.execute("insert into users (id, login) values (11, 'bob')")
        conn.execute(
            "insert into pull_requests (id, repo_id, number, issue_id, user_id) values (100, 1, 1, null, 10)"
        )

        conn.execute(
            "insert into reviews (id, repo_id, user_id, pull_request_id, submitted_at) values (1, 1, 11, 100, '2024-01-10 00:00:00')"
        )
        conn.execute(
            "insert into comments (id, repo_id, user_id, pull_request_id, created_at) values (1, 1, 11, 100, '2024-01-15 00:00:00')"
        )
        conn.commit()
    finally:
        conn.close()

    return repo, data_dir


def _bundle(repo: str) -> PRInputBundle:
    cutoff = datetime(2024, 1, 20, tzinfo=timezone.utc)
    snap = PullRequestSnapshot(
        repo=repo,
        number=1,
        pull_request_id=100,
        author_login="alice",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    return PRInputBundle(
        repo=repo,
        pr_number=1,
        cutoff=cutoff,
        snapshot=snap,
        author_login="alice",
    )


def test_candidate_activity_queries(tmp_path: Path) -> None:
    repo, data_dir = _seed_db(tmp_path)
    conn = connect_repo_db(repo=repo, data_dir=data_dir)
    try:
        repo_id = int(conn.execute("select id from repos where full_name = ?", (repo,)).fetchone()["id"])
        last_ts, counts = candidate_last_activity_and_counts(
            conn=conn,
            repo_id=repo_id,
            candidate_login="bob",
            cutoff=datetime(2024, 1, 20, tzinfo=timezone.utc),
            windows_days=(30, 7),
        )
    finally:
        conn.close()

    assert last_ts is not None
    assert counts[30] == 2
    assert counts[7] == 1


def test_candidate_activity_features(tmp_path: Path) -> None:
    repo, data_dir = _seed_db(tmp_path)
    bundle = _bundle(repo)

    f = build_candidate_activity_features(
        input=bundle,
        candidate_login="bob",
        data_dir=data_dir,
        windows_days=(30, 7),
    )
    assert f["cand.activity.has_prior_event"] is True
    assert f["cand.activity.events_30d"] == 2
    assert f["cand.activity.events_7d"] == 1
    assert "candidate.profile.account_age_days" in f
    assert "candidate.footprint.path_scores.topN" in f
    assert "candidate.activity.load_proxy.open_reviews_est" in f

    table = build_candidate_activity_table(
        input=bundle,
        candidate_logins=["bob", "alice"],
        data_dir=data_dir,
        windows_days=(30,),
    )
    assert list(table.keys()) == ["alice", "bob"]
