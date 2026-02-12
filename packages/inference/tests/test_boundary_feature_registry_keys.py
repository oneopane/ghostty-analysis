from __future__ import annotations

from repo_routing.predictor.features.feature_registry import DEFAULT_FEATURE_REGISTRY


def test_boundary_feature_keys_are_registered() -> None:
    keys = [
        "pr.boundary.set",
        "pr.boundary.count",
        "pr.boundary.boundary_entropy",
        "pair.affinity.boundary_overlap_count",
        "pair.affinity.boundary_overlap_share",
        "pair.affinity.pr_touch_dot_candidate_boundary_atlas",
        "sim.nearest_prs.common_boundaries_topk",
    ]

    for key in keys:
        assert DEFAULT_FEATURE_REGISTRY.resolve(key) is not None
