from __future__ import annotations

from datetime import datetime, timezone

from repo_routing.analysis.models import AnalysisResult, CandidateAnalysis, CandidateFeatures
from repo_routing.parsing.gates import GateFields
from repo_routing.policy.labels import suggest_labels
from repo_routing.scoring.config import LabelsConfig, ScoringConfig


def test_suggest_labels_with_boundaries() -> None:
    result = AnalysisResult(
        repo="acme/widgets",
        pr_number=1,
        cutoff=datetime(2024, 1, 1, tzinfo=timezone.utc),
        gates=GateFields(issue=None, ai_disclosure=None, provenance=None),
        candidates=[
            CandidateAnalysis(
                login="bob",
                score=1.0,
                features=CandidateFeatures(activity_total=1.0, boundary_overlap_activity=1.0),
            )
        ],
        boundaries=["dir:src", "dir:docs"],
        risk="high",
        confidence="low",
    )

    config = ScoringConfig(
        version="v0",
        feature_version="v0",
        weights={"boundary_overlap_activity": 1.0, "activity_total": 0.2},
        thresholds={"confidence_high_margin": 0.2, "confidence_med_margin": 0.1},
        labels=LabelsConfig(include_boundary_labels=True),
    )

    labels = suggest_labels(result, config=config)
    assert "needs-issue-link" in labels
    assert "needs-ai-disclosure" in labels
    assert "needs-provenance" in labels
    assert "routed-high-risk" in labels
    assert "suggested-steward-review" in labels
    assert "routed-boundary:dir:docs" in labels
    assert "routed-boundary:dir:src" in labels
