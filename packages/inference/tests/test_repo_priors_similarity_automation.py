from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from repo_routing.history.models import PullRequestFile, PullRequestSnapshot, ReviewRequest
from repo_routing.inputs.models import PRInputBundle
from repo_routing.predictor.features.automation import build_automation_features
from repo_routing.predictor.features.interaction import build_interaction_features
from repo_routing.predictor.features.repo_priors import build_repo_priors_features
from repo_routing.predictor.features.similarity import build_similarity_features


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
            "create table pull_requests (id integer primary key, repo_id integer, number integer, issue_id integer, user_id integer, created_at text)"
        )
        conn.execute(
            "create table events (id integer primary key, occurred_at text, repo_id integer, actor_id integer, subject_type text, subject_id integer)"
        )
        conn.execute(
            "create table pull_request_head_intervals (id integer primary key, pull_request_id integer, start_event_id integer, end_event_id integer, head_sha text, head_ref text)"
        )
        conn.execute(
            "create table pull_request_files (repo_id integer, pull_request_id integer, head_sha text, path text, status text, additions integer, deletions integer, changes integer)"
        )
        conn.execute(
            "create table reviews (id integer primary key, repo_id integer, user_id integer, pull_request_id integer, submitted_at text)"
        )
        conn.execute(
            "create table comments (id integer primary key, repo_id integer, user_id integer, pull_request_id integer, created_at text, body text)"
        )
        conn.execute(
            "create table pull_request_review_request_intervals (id integer primary key, pull_request_id integer, reviewer_type text, reviewer_id integer, start_event_id integer, end_event_id integer)"
        )

        conn.execute("insert into repos (id, full_name) values (1, ?)", (repo,))
        conn.execute("insert into users (id, login, type) values (10, 'alice', 'User')")
        conn.execute("insert into users (id, login, type) values (11, 'bob', 'User')")
        conn.execute("insert into users (id, login, type) values (12, 'dependabot[bot]', 'Bot')")

        # historical PRs + current PR.
        conn.execute(
            "insert into pull_requests (id, repo_id, number, issue_id, user_id, created_at) values (100, 1, 1, null, 10, '2024-01-01 00:00:00')"
        )
        conn.execute(
            "insert into pull_requests (id, repo_id, number, issue_id, user_id, created_at) values (101, 1, 2, null, 10, '2024-01-03 00:00:00')"
        )
        conn.execute(
            "insert into pull_requests (id, repo_id, number, issue_id, user_id, created_at) values (102, 1, 3, null, 10, '2024-01-05 00:00:00')"
        )

        # events for heads/requests
        for eid, ts, pr in [
            (1, "2024-01-01 00:00:00", 100),
            (2, "2024-01-03 00:00:00", 101),
            (3, "2024-01-05 00:00:00", 102),
        ]:
            conn.execute(
                "insert into events (id, occurred_at, repo_id, actor_id, subject_type, subject_id) values (?, ?, 1, 10, 'pull_request', ?)",
                (eid, ts, pr),
            )

        conn.execute(
            "insert into pull_request_head_intervals (id, pull_request_id, start_event_id, end_event_id, head_sha, head_ref) values (1, 100, 1, null, 'h1', 'main')"
        )
        conn.execute(
            "insert into pull_request_head_intervals (id, pull_request_id, start_event_id, end_event_id, head_sha, head_ref) values (2, 101, 2, null, 'h2', 'main')"
        )
        conn.execute(
            "insert into pull_request_head_intervals (id, pull_request_id, start_event_id, end_event_id, head_sha, head_ref) values (3, 102, 3, null, 'h3', 'main')"
        )

        conn.execute(
            "insert into pull_request_files values (1, 100, 'h1', 'src/a.py', 'modified', 2, 1, 3)"
        )
        conn.execute(
            "insert into pull_request_files values (1, 100, 'h1', 'docs/readme.md', 'modified', 1, 0, 1)"
        )
        conn.execute(
            "insert into pull_request_files values (1, 101, 'h2', 'src/b.py', 'modified', 4, 2, 6)"
        )
        conn.execute(
            "insert into pull_request_files values (1, 102, 'h3', 'src/c.py', 'modified', 3, 1, 4)"
        )
        conn.execute(
            "insert into pull_request_files values (1, 102, 'h3', 'tests/test_c.py', 'added', 8, 0, 8)"
        )

        conn.execute(
            "insert into pull_request_review_request_intervals values (1, 102, 'User', 11, 3, null)"
        )

        # reviews/comments include bot automation comment on current PR.
        conn.execute(
            "insert into reviews values (1, 1, 11, 100, '2024-01-01 12:00:00')"
        )
        conn.execute(
            "insert into reviews values (2, 1, 11, 101, '2024-01-03 10:00:00')"
        )
        conn.execute(
            "insert into reviews values (3, 1, 11, 102, '2024-01-05 12:00:00')"
        )

        conn.execute(
            "insert into comments values (1, 1, 11, 100, '2024-01-01 13:00:00', 'looks good')"
        )
        conn.execute(
            "insert into comments values (2, 1, 12, 102, '2024-01-05 13:00:00', 'dependabot security update')"
        )
        conn.commit()
    finally:
        conn.close()

    return repo, data_dir


def _bundle(repo: str) -> PRInputBundle:
    cutoff = datetime(2024, 1, 6, tzinfo=timezone.utc)
    snap = PullRequestSnapshot(
        repo=repo,
        number=3,
        pull_request_id=102,
        author_login="alice",
        created_at=datetime(2024, 1, 5, tzinfo=timezone.utc),
        title="Add feature",
        body="cc @bob",
        base_sha="base",
        head_sha="h3",
        changed_files=[
            PullRequestFile(path="src/c.py", status="modified", additions=3, deletions=1, changes=4),
            PullRequestFile(path="tests/test_c.py", status="added", additions=8, deletions=0, changes=8),
        ],
        review_requests=[ReviewRequest(reviewer_type="user", reviewer="bob")],
    )
    return PRInputBundle(
        repo=repo,
        pr_number=3,
        cutoff=cutoff,
        snapshot=snap,
        changed_files=list(snap.changed_files),
        review_requests=list(snap.review_requests),
        author_login="alice",
        title=snap.title,
        body=snap.body,
        file_boundaries={"src/c.py": ["dir:src"], "tests/test_c.py": ["dir:tests"]},
        file_boundary_weights={
            "src/c.py": {"dir:src": 1.0},
            "tests/test_c.py": {"dir:tests": 1.0},
        },
        boundaries=["dir:src", "dir:tests"],
    )


def test_repo_priors_similarity_automation_and_pair_social(tmp_path: Path) -> None:
    repo, data_dir = _seed_db(tmp_path)
    bundle = _bundle(repo)

    priors = build_repo_priors_features(input=bundle, data_dir=data_dir)
    assert "repo.priors.median_pr_files_180d" in priors
    assert "pr.surface.files_zscore_vs_repo" in priors

    sim = build_similarity_features(input=bundle, data_dir=data_dir, top_k=2)
    assert len(sim["sim.nearest_prs.topk_ids"]) <= 2
    assert isinstance(sim["sim.nearest_prs.common_reviewers_topk"], list)

    automation = build_automation_features(input=bundle, data_dir=data_dir)
    assert automation["automation.bot_comment_count"] >= 1
    assert automation["automation.has_security_scan_signal"] is True

    interactions = build_interaction_features(
        input=bundle,
        pr_features={"pr.boundary.set": ["dir:src", "dir:tests"], "pr.surface.total_churn": 12, "pr.ownership.owner_set": []},
        candidate_features={
            "bob": {
                "candidate.footprint.boundary_scores.topN": {"dir:src": 1.0},
                "candidate.footprint.dir_depth3_scores.topN": {"src": 1.0},
                "candidate.activity.last_seen_seconds": 10.0,
                "candidate.activity.event_counts_30d": 4,
                "candidate.activity.event_counts_180d": 12,
                "candidate.activity.review_count_180d": 3,
                "candidate.activity.comment_count_180d": 1,
                "cand.activity.events_30d": 4,
            }
        },
        data_dir=str(data_dir),
    )
    assert interactions["bob"]["pair.social.prior_interactions_author_candidate_180d"] >= 1
    assert "pair.social.author_to_candidate_latency_median" in interactions["bob"]
    assert interactions["bob"]["pair.availability.historical_response_rate_bucket"] in {"none", "low", "medium", "high"}
