from __future__ import annotations

from datetime import datetime, timezone
import json

from repo_routing.history.models import PullRequestSnapshot, ReviewRequest
from repo_routing.inputs.models import PRInputBundle
from repo_routing.predictor.feature_extractor_v1 import build_feature_extractor_v1


def _bundle() -> PRInputBundle:
    snap = PullRequestSnapshot(
        repo="acme/widgets",
        number=1,
        pull_request_id=100,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        title="Add endpoint",
        body="cc @bob",
        review_requests=[ReviewRequest(reviewer_type="user", reviewer="carol")],
    )
    return PRInputBundle(
        repo="acme/widgets",
        pr_number=1,
        cutoff=datetime(2024, 1, 2, tzinfo=timezone.utc),
        snapshot=snap,
        title=snap.title,
        body=snap.body,
        review_requests=list(snap.review_requests),
    )


def test_feature_extractor_v1_surface_only() -> None:
    extractor = build_feature_extractor_v1(
        include_pr_timeline_features=False,
        include_ownership_features=False,
        include_candidate_features=False,
    )
    out = extractor.extract(_bundle())

    assert out["feature_version"] == "v1"
    assert out["repo"] == "acme/widgets"
    assert out["pr_number"] == 1
    assert "pr.files.count" in out["pr"]
    assert "pr.silence.no_automation_feedback_pre_cutoff" in out["pr"]
    assert out["candidates"] == {}
    assert out["interactions"] == {}
    assert "labels" in out
    assert "debug" in out


def test_feature_extractor_v1_task_policy_report() -> None:
    extractor = build_feature_extractor_v1(
        include_pr_timeline_features=False,
        include_ownership_features=False,
        include_candidate_features=False,
        task_id="T02",
    )
    out = extractor.extract(_bundle())
    assert "task_policy" in out["meta"]
    assert out["meta"]["task_policy"]["task_id"] == "T02"


def test_feature_extractor_v1_expands_requested_team_from_roster(tmp_path) -> None:  # type: ignore[no-untyped-def]
    bundle = _bundle()
    bundle.review_requests = [
        ReviewRequest(reviewer_type="team", reviewer="acme/reviewers"),
    ]

    roster_path = (
        tmp_path
        / "github"
        / "acme"
        / "widgets"
        / "routing"
        / "team_roster.json"
    )
    roster_path.parent.mkdir(parents=True, exist_ok=True)
    roster_path.write_text(
        json.dumps({"teams": {"acme/reviewers": ["bob", "carol"]}}),
        encoding="utf-8",
    )

    extractor = build_feature_extractor_v1(
        data_dir=tmp_path,
        include_pr_timeline_features=False,
        include_ownership_features=False,
        include_candidate_features=False,
    )
    out = extractor.extract(bundle)

    assert out["meta"]["candidate_teams"] == ["acme/reviewers"]
    assert out["meta"]["candidate_logins"] == ["bob", "carol"]
