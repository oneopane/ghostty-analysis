from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import Any, Literal

ValueType = Literal[
    "binary",
    "categorical",
    "ordinal",
    "count",
    "real",
    "set",
    "sequence",
]
TemporalSemantics = Literal[
    "static_at_cutoff",
    "recency_based",
    "cumulative",
    "derived_snapshot",
]
Granularity = Literal["pr", "candidate", "pair", "set"]
FeatureRole = Literal["gate", "context", "ranking", "calibration"]


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    value_type: ValueType
    temporal_semantics: TemporalSemantics
    granularity: Granularity
    role: FeatureRole
    description: str = ""
    deprecated: bool = False


class FeatureRegistry:
    def __init__(self, *, version: str = "fr.v1") -> None:
        self.version = version
        self._specs: dict[str, FeatureSpec] = {}
        self._patterns: dict[str, FeatureSpec] = {}

    def register(self, spec: FeatureSpec, *, pattern: bool = False) -> None:
        if pattern:
            self._patterns[spec.name] = spec
        else:
            self._specs[spec.name] = spec

    def resolve(self, feature_key: str) -> FeatureSpec | None:
        exact = self._specs.get(feature_key)
        if exact is not None:
            return exact
        for pat, spec in sorted(self._patterns.items(), key=lambda kv: kv[0]):
            if fnmatch.fnmatch(feature_key, pat):
                return spec
        return None

    def classify_many(self, keys: list[str]) -> dict[str, FeatureSpec | None]:
        return {k: self.resolve(k) for k in sorted(set(keys))}

    def coverage(self, keys: list[str]) -> dict[str, Any]:
        classified = self.classify_many(keys)
        unresolved = sorted([k for k, v in classified.items() if v is None])
        return {
            "registry_version": self.version,
            "feature_count": len(classified),
            "resolved_count": len(classified) - len(unresolved),
            "unresolved_count": len(unresolved),
            "unresolved_keys": unresolved,
        }


def flatten_extracted_feature_keys(payload: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    pr = payload.get("pr")
    if isinstance(pr, dict):
        keys.extend(str(k) for k in pr.keys())

    candidates = payload.get("candidates")
    if isinstance(candidates, dict):
        for _login, feats in sorted(candidates.items(), key=lambda kv: str(kv[0]).lower()):
            if isinstance(feats, dict):
                keys.extend(str(k) for k in feats.keys())

    interactions = payload.get("interactions")
    if isinstance(interactions, dict):
        for _login, feats in sorted(interactions.items(), key=lambda kv: str(kv[0]).lower()):
            if isinstance(feats, dict):
                keys.extend(str(k) for k in feats.keys())

    return sorted(set(keys))


def default_feature_registry() -> FeatureRegistry:
    r = FeatureRegistry(version="fr.v1")

    # PR meta/context
    r.register(FeatureSpec("pr.meta.author_type", "categorical", "static_at_cutoff", "pr", "context"))
    r.register(FeatureSpec("pr.meta.created_at_ts", "count", "static_at_cutoff", "pr", "context"))
    r.register(FeatureSpec("pr.meta.is_draft", "binary", "derived_snapshot", "pr", "gate"))
    r.register(FeatureSpec("pr.meta.title_has_wip_signal", "binary", "static_at_cutoff", "pr", "gate"))
    r.register(FeatureSpec("pr.meta.title_has_hotfix_signal", "binary", "static_at_cutoff", "pr", "context"))
    r.register(FeatureSpec("pr.meta.mentions.count", "count", "static_at_cutoff", "pr", "context"))

    # PR surface
    r.register(FeatureSpec("pr.surface.changed_file_count", "count", "static_at_cutoff", "pr", "ranking"))
    r.register(FeatureSpec("pr.surface.total_churn", "count", "static_at_cutoff", "pr", "ranking"))
    r.register(FeatureSpec("pr.surface.max_file_churn", "count", "static_at_cutoff", "pr", "ranking"))
    r.register(FeatureSpec("pr.surface.median_file_churn", "real", "static_at_cutoff", "pr", "ranking"))
    r.register(FeatureSpec("pr.surface.status_ratio.*", "real", "static_at_cutoff", "pr", "context"), pattern=True)
    r.register(FeatureSpec("pr.surface.distinct_directories_count.*", "count", "static_at_cutoff", "pr", "context"), pattern=True)
    r.register(FeatureSpec("pr.surface.directory_entropy.*", "real", "static_at_cutoff", "pr", "context"), pattern=True)
    r.register(FeatureSpec("pr.surface.extension_entropy", "real", "static_at_cutoff", "pr", "context"))
    r.register(FeatureSpec("pr.surface.touches_*", "binary", "static_at_cutoff", "pr", "context"), pattern=True)

    # Gates / ownership / areas
    r.register(FeatureSpec("pr.gates.*", "binary", "static_at_cutoff", "pr", "gate"), pattern=True)
    r.register(FeatureSpec("pr.gates.completeness_score", "real", "static_at_cutoff", "pr", "calibration"))
    r.register(FeatureSpec("pr.areas.set", "set", "static_at_cutoff", "set", "context"))
    r.register(FeatureSpec("pr.areas.count", "count", "static_at_cutoff", "pr", "context"))
    r.register(FeatureSpec("pr.areas.area_entropy", "real", "static_at_cutoff", "pr", "context"))
    r.register(FeatureSpec("pr.ownership.owner_set", "set", "derived_snapshot", "set", "context"))
    r.register(FeatureSpec("pr.ownership.owner_set_size", "count", "derived_snapshot", "pr", "context"))
    r.register(FeatureSpec("pr.ownership.owner_coverage_ratio", "real", "derived_snapshot", "pr", "calibration"))

    # Trajectory / attention / request overlap
    r.register(FeatureSpec("pr.trajectory.*", "count", "cumulative", "pr", "context"), pattern=True)
    r.register(FeatureSpec("pr.trajectory.time_since_last_head_update_seconds", "real", "recency_based", "pr", "context"))
    r.register(FeatureSpec("pr.trajectory.head_update_burstiness", "real", "recency_based", "pr", "context"))
    r.register(FeatureSpec("pr.attention.*", "count", "cumulative", "pr", "calibration"), pattern=True)
    r.register(FeatureSpec("pr.request_overlap.*", "real", "derived_snapshot", "pr", "context"), pattern=True)

    # Repo priors and similarity
    r.register(FeatureSpec("repo.priors.*", "real", "derived_snapshot", "pr", "calibration"), pattern=True)
    r.register(FeatureSpec("sim.nearest_prs.topk_ids", "set", "derived_snapshot", "set", "context"))
    r.register(FeatureSpec("sim.nearest_prs.mean_ttfr_topk", "real", "derived_snapshot", "pr", "calibration"))
    r.register(FeatureSpec("sim.nearest_prs.owner_overlap_rate_topk", "real", "derived_snapshot", "pr", "calibration"))
    r.register(FeatureSpec("sim.nearest_prs.common_reviewers_topk", "set", "derived_snapshot", "set", "context"))
    r.register(FeatureSpec("sim.nearest_prs.common_areas_topk", "set", "derived_snapshot", "set", "context"))

    # Candidate
    r.register(FeatureSpec("candidate.profile.type", "categorical", "static_at_cutoff", "candidate", "context"))
    r.register(FeatureSpec("candidate.profile.is_bot", "binary", "static_at_cutoff", "candidate", "gate"))
    r.register(FeatureSpec("candidate.profile.account_age_days", "real", "recency_based", "candidate", "context"))
    r.register(FeatureSpec("candidate.activity.last_seen_seconds", "real", "recency_based", "candidate", "ranking"))
    r.register(FeatureSpec("candidate.activity.event_counts_*", "count", "recency_based", "candidate", "ranking"), pattern=True)
    r.register(FeatureSpec("candidate.activity.*_180d", "count", "cumulative", "candidate", "ranking"), pattern=True)
    r.register(FeatureSpec("candidate.activity.load_proxy.open_reviews_est", "count", "derived_snapshot", "candidate", "calibration"))
    r.register(FeatureSpec("candidate.footprint.*", "set", "derived_snapshot", "candidate", "context"), pattern=True)

    # Pair features (core ranking)
    r.register(FeatureSpec("pair.affinity.*", "real", "derived_snapshot", "pair", "ranking"), pattern=True)
    r.register(FeatureSpec("pair.social.*", "real", "cumulative", "pair", "ranking"), pattern=True)
    r.register(FeatureSpec("pair.availability.recency_seconds", "real", "recency_based", "pair", "ranking"))
    r.register(FeatureSpec("pair.availability.historical_response_rate_bucket", "ordinal", "derived_snapshot", "pair", "calibration"))
    r.register(FeatureSpec("pair.availability.is_already_participating", "binary", "cumulative", "pair", "context"))

    # Automation
    r.register(FeatureSpec("automation.bot_comment_count", "count", "cumulative", "pr", "context"))
    r.register(FeatureSpec("automation.bot_authors.distinct_count", "count", "cumulative", "pr", "context"))
    r.register(FeatureSpec("automation.bot_categories.*", "count", "cumulative", "pr", "context"), pattern=True)
    r.register(FeatureSpec("automation.has_*", "binary", "cumulative", "pr", "context"), pattern=True)

    # Labels/debug
    r.register(FeatureSpec("labels.*", "binary", "derived_snapshot", "pr", "calibration"), pattern=True)
    r.register(FeatureSpec("debug.*", "categorical", "static_at_cutoff", "pr", "context"), pattern=True)

    # Legacy aliases, still classifiable.
    r.register(FeatureSpec("pr.files.*", "count", "static_at_cutoff", "pr", "context", deprecated=True), pattern=True)
    r.register(FeatureSpec("pr.churn.*", "count", "static_at_cutoff", "pr", "context", deprecated=True), pattern=True)
    r.register(FeatureSpec("pr.paths.*", "real", "static_at_cutoff", "pr", "context", deprecated=True), pattern=True)
    r.register(FeatureSpec("pr.text.*", "real", "static_at_cutoff", "pr", "context", deprecated=True), pattern=True)
    r.register(FeatureSpec("pr.timeline.*", "real", "cumulative", "pr", "context", deprecated=True), pattern=True)
    r.register(FeatureSpec("pr.owners.*", "real", "derived_snapshot", "pr", "context", deprecated=True), pattern=True)
    r.register(FeatureSpec("cand.activity.*", "real", "recency_based", "candidate", "context", deprecated=True), pattern=True)
    r.register(FeatureSpec("x.*", "real", "derived_snapshot", "pair", "ranking", deprecated=True), pattern=True)

    return r


DEFAULT_FEATURE_REGISTRY = default_feature_registry()
