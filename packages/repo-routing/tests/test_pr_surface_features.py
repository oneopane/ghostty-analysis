from __future__ import annotations

from datetime import datetime, timezone

from repo_routing.history.models import PullRequestFile, PullRequestSnapshot, ReviewRequest
from repo_routing.inputs.models import PRGateFields, PRInputBundle
from repo_routing.predictor.features.pr_surface import build_pr_surface_features
from repo_routing.predictor.features.stats import median_int, normalized_entropy, safe_ratio


def _bundle() -> PRInputBundle:
    cutoff = datetime(2024, 1, 2, tzinfo=timezone.utc)
    snapshot = PullRequestSnapshot(
        repo="acme/widgets",
        number=1,
        pull_request_id=101,
        issue_id=None,
        author_login="alice",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        title="WIP: add tests",
        body="Issue: #1\nAI: no\nProvenance: human\ncc @bob\nhttps://example.com",
        base_sha="base",
        head_sha="head",
        changed_files=[
            PullRequestFile(path="src/app.py", status="modified", additions=3, deletions=1, changes=4),
            PullRequestFile(path="tests/test_app.py", status="added", additions=10, deletions=0, changes=10),
            PullRequestFile(path="docs/readme.md", status="modified", additions=2, deletions=1, changes=3),
        ],
        review_requests=[ReviewRequest(reviewer_type="user", reviewer="bob")],
    )
    return PRInputBundle(
        repo="acme/widgets",
        pr_number=1,
        cutoff=cutoff,
        snapshot=snapshot,
        changed_files=list(snapshot.changed_files),
        review_requests=list(snapshot.review_requests),
        author_login="alice",
        title=snapshot.title,
        body=snapshot.body,
        gate_fields=PRGateFields(
            issue="#1",
            ai_disclosure="AI: no",
            provenance="Provenance: human",
            missing_issue=False,
            missing_ai_disclosure=False,
            missing_provenance=False,
        ),
        file_areas={
            "src/app.py": "src",
            "tests/test_app.py": "tests",
            "docs/readme.md": "docs",
        },
        areas=["docs", "src", "tests"],
    )


def test_stats_helpers() -> None:
    assert safe_ratio(1.0, 0.0) == 0.0
    assert median_int([]) == 0.0
    assert median_int([1, 3, 2]) == 2.0
    assert median_int([1, 3, 2, 4]) == 2.5
    assert normalized_entropy([3, 0, 0]) == 0.0
    assert 0.0 < normalized_entropy([1, 1, 1]) <= 1.0


def test_build_pr_surface_features() -> None:
    features = build_pr_surface_features(_bundle())

    assert features["pr.files.count"] == 3
    assert features["pr.churn.additions_total"] == 15
    assert features["pr.churn.deletions_total"] == 2
    assert features["pr.churn.total"] == 17
    assert features["pr.paths.touches_tests"] is True
    assert features["pr.paths.touches_docs"] is True
    assert features["pr.areas.count"] == 3
    assert features["pr.areas.is_multi"] is True
    assert features["pr.text.mention_count"] == 1
    assert features["pr.text.url_count"] == 1
    assert features["pr.gates.completeness_score"] == 1.0
