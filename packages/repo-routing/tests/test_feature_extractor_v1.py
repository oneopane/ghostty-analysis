from __future__ import annotations

from datetime import datetime, timezone

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
    assert out["candidates"] == {}
    assert out["interactions"] == {}
