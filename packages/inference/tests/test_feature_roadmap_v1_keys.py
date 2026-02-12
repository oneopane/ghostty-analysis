from __future__ import annotations

from datetime import datetime, timezone

from repo_routing.history.models import PullRequestFile, PullRequestSnapshot, ReviewRequest
from repo_routing.inputs.models import PRGateFields, PRInputBundle
from repo_routing.predictor.features.interaction import build_interaction_features
from repo_routing.predictor.features.ownership import build_ownership_features
from repo_routing.predictor.features.pr_surface import build_pr_surface_features


def _bundle() -> PRInputBundle:
    cutoff = datetime(2024, 1, 2, tzinfo=timezone.utc)
    snapshot = PullRequestSnapshot(
        repo="acme/widgets",
        number=1,
        pull_request_id=101,
        issue_id=None,
        author_login="alice",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        title="WIP hotfix: add tests",
        body="Issue: #1\nAI: no\nProvenance: human\ncc @bob @acme/reviewers\nhttps://example.com",
        base_ref="main",
        base_sha="base",
        head_sha="head",
        changed_files=[
            PullRequestFile(path="src/app.py", status="modified", additions=3, deletions=1, changes=4),
            PullRequestFile(path="tests/test_app.py", status="added", additions=10, deletions=0, changes=10),
            PullRequestFile(path="docs/readme.md", status="renamed", additions=2, deletions=1, changes=3),
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


def test_v1_namespace_keys_exist(tmp_path) -> None:  # type: ignore[no-untyped-def]
    bundle = _bundle()
    pr = build_pr_surface_features(bundle)

    assert "pr.meta.base_ref" in pr
    assert "pr.meta.title_has_hotfix_signal" in pr
    assert "pr.surface.directory_entropy.depth3" in pr
    assert "pr.surface.status_ratio.renamed" in pr
    assert "pr.geometry.shape.area_entropy" in pr
    assert "pr.gates.has_risk_section" in pr
    assert "pr.areas.set" in pr

    ownership = build_ownership_features(bundle, data_dir=tmp_path, active_candidates={"bob"})
    assert "pr.ownership.owner_set" in ownership
    assert "pr.ownership.owner_coverage_ratio" in ownership

    interactions = build_interaction_features(
        input=bundle,
        pr_features={**pr, **ownership},
        candidate_features={
            "bob": {
                "candidate.footprint.area_scores.topN": {"src": 0.7, "docs": 0.3},
                "candidate.footprint.dir_depth3_scores.topN": {"src": 0.7, "docs": 0.3},
                "candidate.activity.last_seen_seconds": 100.0,
                "candidate.activity.review_count_180d": 10,
                "candidate.activity.comment_count_180d": 2,
                "cand.activity.events_30d": 2,
            }
        },
    )
    assert "pair.affinity.area_overlap_count" in interactions["bob"]
    assert "pair.affinity.pr_touch_dot_candidate_area_atlas" in interactions["bob"]
