from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from repo_routing.history.models import PullRequestSnapshot, ReviewRequest
from repo_routing.inputs.models import PRInputBundle
from repo_routing.predictor.feature_extractor_v1 import build_feature_extractor_v1
from repo_routing.predictor.features.candidate_activity import build_candidate_activity_features
from repo_routing.predictor.features.pr_timeline import build_pr_timeline_features


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
            "create table events (id integer primary key, occurred_at text, repo_id integer, actor_id integer, subject_type text, subject_id integer)"
        )
        conn.execute(
            "create table pull_request_draft_intervals (id integer primary key, pull_request_id integer, is_draft integer, start_event_id integer, end_event_id integer)"
        )
        conn.execute(
            "create table pull_request_head_intervals (id integer primary key, pull_request_id integer, start_event_id integer, end_event_id integer, head_sha text, head_ref text)"
        )
        conn.execute(
            "create table pull_request_review_request_intervals (id integer primary key, pull_request_id integer, reviewer_type text, reviewer_id integer, start_event_id integer, end_event_id integer)"
        )
        conn.execute(
            "create table comments (id integer primary key, repo_id integer, user_id integer, pull_request_id integer, created_at text)"
        )
        conn.execute(
            "create table reviews (id integer primary key, repo_id integer, user_id integer, pull_request_id integer, submitted_at text)"
        )

        conn.execute("insert into repos (id, full_name) values (1, ?)", (repo,))
        conn.execute("insert into users (id, login) values (10, 'alice')")
        conn.execute("insert into users (id, login) values (11, 'bob')")
        conn.execute(
            "insert into pull_requests (id, repo_id, number, issue_id, user_id) values (100, 1, 1, null, 10)"
        )

        # Pre-cutoff events
        conn.execute(
            "insert into events (id, occurred_at, repo_id, actor_id, subject_type, subject_id) values (1, '2024-01-01 00:00:00', 1, 10, 'pull_request', 100)"
        )
        conn.execute(
            "insert into events (id, occurred_at, repo_id, actor_id, subject_type, subject_id) values (2, '2024-01-02 00:00:00', 1, 10, 'pull_request', 100)"
        )
        conn.execute(
            "insert into events (id, occurred_at, repo_id, actor_id, subject_type, subject_id) values (3, '2024-01-03 00:00:00', 1, 10, 'pull_request', 100)"
        )

        # Post-cutoff events that must NOT influence features at cutoff=2024-01-06.
        conn.execute(
            "insert into events (id, occurred_at, repo_id, actor_id, subject_type, subject_id) values (4, '2024-01-10 00:00:00', 1, 10, 'pull_request', 100)"
        )
        conn.execute(
            "insert into events (id, occurred_at, repo_id, actor_id, subject_type, subject_id) values (5, '2024-01-11 00:00:00', 1, 10, 'pull_request', 100)"
        )

        # Draft intervals: draft=True until post-cutoff transition to draft=False.
        conn.execute(
            "insert into pull_request_draft_intervals (id, pull_request_id, is_draft, start_event_id, end_event_id) values (1, 100, 1, 1, 5)"
        )
        conn.execute(
            "insert into pull_request_draft_intervals (id, pull_request_id, is_draft, start_event_id, end_event_id) values (2, 100, 0, 5, null)"
        )

        # Head updates: one before, one after cutoff.
        conn.execute(
            "insert into pull_request_head_intervals (id, pull_request_id, start_event_id, end_event_id, head_sha, head_ref) values (1, 100, 2, 4, 'head1', 'main')"
        )
        conn.execute(
            "insert into pull_request_head_intervals (id, pull_request_id, start_event_id, end_event_id, head_sha, head_ref) values (2, 100, 4, null, 'head2', 'main')"
        )

        # Active request before cutoff.
        conn.execute(
            "insert into pull_request_review_request_intervals (id, pull_request_id, reviewer_type, reviewer_id, start_event_id, end_event_id) values (1, 100, 'User', 11, 3, null)"
        )

        # Comments/reviews both pre and post cutoff.
        conn.execute(
            "insert into comments (id, repo_id, user_id, pull_request_id, created_at) values (1, 1, 10, 100, '2024-01-04 00:00:00')"
        )
        conn.execute(
            "insert into comments (id, repo_id, user_id, pull_request_id, created_at) values (2, 1, 11, 100, '2024-01-05 00:00:00')"
        )
        conn.execute(
            "insert into comments (id, repo_id, user_id, pull_request_id, created_at) values (3, 1, 11, 100, '2024-01-12 00:00:00')"
        )

        conn.execute(
            "insert into reviews (id, repo_id, user_id, pull_request_id, submitted_at) values (1, 1, 11, 100, '2024-01-05 00:00:00')"
        )
        conn.execute(
            "insert into reviews (id, repo_id, user_id, pull_request_id, submitted_at) values (2, 1, 11, 100, '2024-01-13 00:00:00')"
        )

        conn.commit()
    finally:
        conn.close()

    return repo, data_dir


def _bundle(repo: str) -> PRInputBundle:
    cutoff = datetime(2024, 1, 6, tzinfo=timezone.utc)
    snap = PullRequestSnapshot(
        repo=repo,
        number=1,
        pull_request_id=100,
        author_login="alice",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        title="Add API",
        body="cc @bob",
        review_requests=[ReviewRequest(reviewer_type="user", reviewer="bob")],
    )
    return PRInputBundle(
        repo=repo,
        pr_number=1,
        cutoff=cutoff,
        snapshot=snap,
        author_login="alice",
        title=snap.title,
        body=snap.body,
        review_requests=list(snap.review_requests),
    )


def _stable_json_bytes(obj: object) -> bytes:
    return (
        json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        .encode("utf-8")
    )


def test_cutoff_leakage_timeline_and_candidate_features(tmp_path: Path) -> None:
    repo, data_dir = _seed_db(tmp_path)
    bundle = _bundle(repo)

    timeline = build_pr_timeline_features(bundle, data_dir=str(data_dir), codeowner_logins={"bob"})
    assert timeline["pr.timeline.is_draft_at_cutoff"] is True
    assert timeline["pr.timeline.head_updates_pre_cutoff"] == 1
    assert timeline["pr.timeline.non_author_comments_pre_cutoff"] == 1
    assert timeline["pr.timeline.reviews_pre_cutoff"] == 1

    cand = build_candidate_activity_features(
        input=bundle,
        candidate_login="bob",
        data_dir=data_dir,
        windows_days=(30,),
    )
    # Includes pre-cutoff review+comment only; excludes post-cutoff review/comment.
    assert cand["cand.activity.events_30d"] == 2


def test_feature_extractor_deterministic_output_bytes(tmp_path: Path) -> None:
    repo, data_dir = _seed_db(tmp_path)
    bundle = _bundle(repo)

    extractor = build_feature_extractor_v1(
        data_dir=data_dir,
        include_pr_timeline_features=True,
        include_ownership_features=False,
        include_candidate_features=True,
    )

    out1 = extractor.extract(bundle)
    out2 = extractor.extract(bundle)

    assert out1 == out2
    assert _stable_json_bytes(out1) == _stable_json_bytes(out2)
