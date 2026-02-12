from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from repo_routing.inputs.builder import build_pr_input_bundle
from repo_routing.time import parse_dt_utc


def _seed_db(tmp_path: Path) -> tuple[str, Path]:
    repo = "acme/widgets"
    owner, name = repo.split("/", 1)
    db_path = tmp_path / "data" / "github" / owner / name / "history.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("create table repos (id integer primary key, full_name text)")
        conn.execute("create table users (id integer primary key, login text, type text)")
        conn.execute(
            "create table pull_requests (id integer primary key, repo_id integer, issue_id integer, number integer, user_id integer, created_at text, title text, body text, base_sha text, base_ref text)"
        )
        conn.execute(
            "create table events (id integer primary key, occurred_at text)"
        )
        conn.execute(
            "create table pull_request_head_intervals (id integer primary key, pull_request_id integer, head_sha text, head_ref text, start_event_id integer, end_event_id integer)"
        )
        conn.execute(
            "create table pull_request_files (repo_id integer, pull_request_id integer, head_sha text, path text, status text, additions integer, deletions integer, changes integer)"
        )
        conn.execute(
            "create table pull_request_review_request_intervals (id integer primary key, pull_request_id integer, reviewer_type text, reviewer_id integer, start_event_id integer, end_event_id integer)"
        )
        conn.execute("create table teams (id integer primary key, slug text)")

        conn.execute("insert into repos (id, full_name) values (1, ?)", (repo,))
        conn.execute("insert into users (id, login, type) values (1, 'alice', 'User')")
        conn.execute("insert into users (id, login, type) values (2, 'bob', 'User')")

        conn.execute(
            "insert into pull_requests (id, repo_id, issue_id, number, user_id, created_at, title, body, base_sha, base_ref) values (101, 1, null, 1, 1, '2024-01-01 00:00:00', 'T', 'Issue: #1', 'base', 'main')"
        )
        conn.execute("insert into events (id, occurred_at) values (1, '2024-01-01 00:00:00')")
        conn.execute(
            "insert into pull_request_head_intervals (id, pull_request_id, head_sha, head_ref, start_event_id, end_event_id) values (1, 101, 'head', 'main', 1, null)"
        )
        conn.execute(
            "insert into pull_request_files (repo_id, pull_request_id, head_sha, path, status, additions, deletions, changes) values (1, 101, 'head', 'src/a.py', 'modified', 1, 1, 2)"
        )
        conn.execute(
            "insert into pull_request_review_request_intervals (id, pull_request_id, reviewer_type, reviewer_id, start_event_id, end_event_id) values (1, 101, 'User', 2, 1, null)"
        )
        conn.commit()
    finally:
        conn.close()

    return repo, db_path.parent.parent.parent.parent


def test_pr_input_bundle_deterministic_json(tmp_path: Path) -> None:
    repo, data_dir = _seed_db(tmp_path)
    cutoff = parse_dt_utc("2024-01-02T00:00:00Z")
    assert cutoff is not None

    b1 = build_pr_input_bundle(repo, 1, cutoff, data_dir)
    b2 = build_pr_input_bundle(repo, 1, cutoff, data_dir)

    j1 = json.dumps(b1.model_dump(mode="json"), sort_keys=True, ensure_ascii=True)
    j2 = json.dumps(b2.model_dump(mode="json"), sort_keys=True, ensure_ascii=True)
    assert j1 == j2
    assert b1.boundaries == []
    assert b1.file_boundaries == {}
