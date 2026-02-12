from __future__ import annotations

from repo_routing.predictor.features.feature_registry import DEFAULT_FEATURE_REGISTRY
from repo_routing.predictor.features.task_policy import DEFAULT_TASK_POLICY_REGISTRY


def test_task_policy_registry_contains_expected_tasks() -> None:
    ids = DEFAULT_TASK_POLICY_REGISTRY.list_ids()
    assert "T02" in ids
    assert "T04" in ids
    assert "T06" in ids


def test_t06_allows_pair_affinity_and_candidate_activity() -> None:
    report = DEFAULT_TASK_POLICY_REGISTRY.evaluate(
        task_id="T06",
        feature_keys=[
            "pair.affinity.boundary_overlap_count",
            "pair.availability.recency_seconds",
            "candidate.activity.event_counts_30d",
            "pr.boundary.count",
        ],
        feature_registry=DEFAULT_FEATURE_REGISTRY,
    )
    assert report["violation_count"] == 0
    assert report["unresolved_count"] == 0


def test_t02_rejects_pair_ranking_features() -> None:
    report = DEFAULT_TASK_POLICY_REGISTRY.evaluate(
        task_id="T02",
        feature_keys=[
            "pr.meta.is_draft",
            "pr.gates.completeness_score",
            "pair.affinity.boundary_overlap_count",  # should be disallowed for readiness
        ],
        feature_registry=DEFAULT_FEATURE_REGISTRY,
    )
    assert report["violation_count"] >= 1
    assert "pair.affinity.boundary_overlap_count" in report["violations"]
