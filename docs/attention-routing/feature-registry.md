# Feature Registry and Task Policy

This document describes the metadata registry used to classify extracted features and enforce task-specific feature policies.

For conceptual PR×X relation buckets, see `relation-taxonomy.md`.

Code:

- `packages/repo-routing/src/repo_routing/predictor/features/feature_registry.py`
- `packages/repo-routing/src/repo_routing/predictor/features/task_policy.py`

## 1) Feature taxonomy model

Each feature is described by `FeatureSpec`:

- `name`
- `value_type`: `binary | categorical | ordinal | count | real | set | sequence`
- `temporal_semantics`: `static_at_cutoff | recency_based | cumulative | derived_snapshot`
- `granularity`: `pr | candidate | pair | set`
- `role`: `gate | context | ranking | calibration`
- `deprecated` (optional)

Both exact keys and wildcard patterns are supported.

Examples:

- `pr.meta.is_draft` → `binary`, `derived_snapshot`, `pr`, `gate`
- `pair.affinity.*` → `real`, `derived_snapshot`, `pair`, `ranking`
- `candidate.activity.event_counts_*` → `count`, `recency_based`, `candidate`, `ranking`
- `pr.silence.*` → `binary`, `derived_snapshot`, `pr`, `calibration`
- `pr.geometry.*` → `real`, `derived_snapshot`, `pr`, `context`

## 2) Runtime coverage reporting

Extractor output includes:

- `meta.feature_registry.registry_version`
- `meta.feature_registry.feature_count`
- `meta.feature_registry.resolved_count`
- `meta.feature_registry.unresolved_count`
- `meta.feature_registry.unresolved_keys`

This is computed from all keys in:

- `pr`
- `candidates[*]`
- `interactions[*]`

Purpose:

- detect schema drift,
- ensure newly introduced features are classified,
- surface missing registry entries in artifacts.

## 3) Task policy model

Each task policy is represented by `TaskPolicySpec`:

- `task_id`
- `name`
- `allowed_roles`
- `allowed_granularities`
- `allowed_prefixes`
- `recommended_model`

Registered defaults:

- `T02`: review readiness
- `T04`: owner coverage confidence
- `T06`: first responder routing
- `T09`: stall risk
- `T10`: reviewer set sizing

## 4) Task policy evaluation

When extractor config sets `task_id`, output includes:

- `meta.task_policy.task_policy_version`
- `meta.task_policy.task_id`
- `meta.task_policy.recommended_model`
- `meta.task_policy.unresolved_keys`
- `meta.task_policy.violations`

Violation reasons:

- `prefix_not_allowed`
- `role_not_allowed`
- `granularity_not_allowed`

## 5) How to use in practice

1. Add or modify a feature.
2. Register/update its `FeatureSpec`.
3. Run extraction and inspect `meta.feature_registry.unresolved_count`.
4. For a task-specific run, set `task_id` and inspect `meta.task_policy.violation_count`.
5. Keep policy-compliant subsets for baseline models and ablations.

## 6) Compatibility notes

Legacy keys are still classified (marked deprecated patterns), including:

- `pr.files.*`, `pr.churn.*`, `pr.paths.*`, `pr.text.*`
- `pr.timeline.*`, `pr.owners.*`
- `cand.activity.*`, `x.*`

This keeps old artifacts usable while migrating to canonical names.
