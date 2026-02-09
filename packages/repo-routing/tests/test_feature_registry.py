from __future__ import annotations

from datetime import datetime, timezone

from repo_routing.history.models import PullRequestSnapshot
from repo_routing.inputs.models import PRInputBundle
from repo_routing.predictor.feature_extractor_v1 import build_feature_extractor_v1
from repo_routing.predictor.features.feature_registry import (
    DEFAULT_FEATURE_REGISTRY,
    FeatureSpec,
    FeatureRegistry,
)


def test_feature_registry_resolve_exact_and_pattern() -> None:
    reg = FeatureRegistry()
    reg.register(
        FeatureSpec(
            name="pr.surface.total_churn",
            value_type="count",
            temporal_semantics="static_at_cutoff",
            granularity="pr",
            role="ranking",
        )
    )
    reg.register(
        FeatureSpec(
            name="candidate.activity.event_counts_*",
            value_type="count",
            temporal_semantics="recency_based",
            granularity="candidate",
            role="ranking",
        ),
        pattern=True,
    )

    assert reg.resolve("pr.surface.total_churn") is not None
    assert reg.resolve("candidate.activity.event_counts_30d") is not None
    assert reg.resolve("does.not.exist") is None


def test_default_registry_has_key_dimensions() -> None:
    spec = DEFAULT_FEATURE_REGISTRY.resolve("pair.affinity.area_overlap_count")
    assert spec is not None
    assert spec.granularity == "pair"
    assert spec.role == "ranking"


def test_extractor_emits_registry_coverage() -> None:
    snap = PullRequestSnapshot(
        repo="acme/widgets",
        number=1,
        pull_request_id=100,
        title="Add endpoint",
        body="cc @bob",
    )
    bundle = PRInputBundle(
        repo="acme/widgets",
        pr_number=1,
        cutoff=datetime(2024, 1, 2, tzinfo=timezone.utc),
        snapshot=snap,
        title=snap.title,
        body=snap.body,
    )

    extractor = build_feature_extractor_v1(
        include_pr_timeline_features=False,
        include_ownership_features=False,
        include_candidate_features=False,
    )
    out = extractor.extract(bundle)

    coverage = out["meta"]["feature_registry"]
    assert coverage["registry_version"] == "fr.v1"
    assert coverage["feature_count"] >= 1
    assert coverage["resolved_count"] >= 1
