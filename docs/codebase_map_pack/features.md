# Features

This repo has two feature surfaces relevant to PR/SDLC analytics:

1) Router-internal features used by heuristic/baseline routers (e.g. stewards analysis) that are not emitted as a canonical feature vector.
2) A structured feature extractor (`AttentionRoutingFeatureExtractorV1`) + feature registry, designed to emit cutoff-safe `pr`, `candidate`, and `pair` features when a router is implemented as a `PipelinePredictor`.

## Feature Registry (Canonical Key Taxonomy) {#feature-registry}

Registry:

- `packages/inference/src/repo_routing/predictor/features/feature_registry.py`

Extractor:

- `packages/inference/src/repo_routing/predictor/feature_extractor_v1.py`

Task policy constraints (allowlists by task id):

- `packages/inference/src/repo_routing/predictor/features/task_policy.py`

Quality scanner for unresolved/violating keys:

- `scripts/check_feature_quality.py`

## Feature Families {#feature-families}

The registry is mostly pattern-based; `name` can be an exact key or a wildcard pattern.

| Registry Key/Pattern | Entity | Temporal Semantics | Computed In |
|---|---|---|---|
| `pr.meta.*` | PR | static_at_cutoff / derived_snapshot | `repo_routing/predictor/features/pr_surface.py`, `repo_routing/predictor/features/pr_timeline.py` |
| `pr.surface.*` | PR | static_at_cutoff | `repo_routing/predictor/features/pr_surface.py` |
| `pr.gates.*` | PR | static_at_cutoff | `repo_routing/inputs/builder.py` (gate parse), `repo_routing/predictor/features/pr_surface.py` |
| `pr.boundary.*` | PR | static_at_cutoff | `repo_routing/inputs/builder.py` (boundary footprint) |
| `pr.ownership.*` | PR | derived_snapshot | `repo_routing/predictor/features/ownership.py` |
| `pr.trajectory.*`, `pr.attention.*` | PR | cumulative / recency_based | `repo_routing/predictor/features/pr_timeline.py` |
| `repo.priors.*` | PR-context | derived_snapshot | `repo_routing/predictor/features/repo_priors.py` |
| `sim.nearest_prs.*` | PR-context | derived_snapshot | `repo_routing/predictor/features/similarity.py` |
| `candidate.*` | Candidate | recency_based / cumulative / derived_snapshot | `repo_routing/predictor/features/candidate_activity.py` |
| `pair.*` | Pair | derived_snapshot / cumulative / recency_based | `repo_routing/predictor/features/interaction.py` |
| `automation.*` | PR | cumulative | `repo_routing/predictor/features/automation.py` |

## Known-By-Time Semantics

- `static_at_cutoff`: computed from as-of PR snapshot and/or as-of DB queries.
- `cumulative`: aggregates all events up to `cutoff`.
- `recency_based`: aggregates in a pre-cutoff window (e.g. 7/30/90/180 days), with explicit bounds `<= cutoff`.
- `derived_snapshot`: computed as a deterministic function of other cutoff-safe values (including pinned artifacts keyed by PR base SHA, and boundary artifacts keyed by cutoff).

## Leakage Notes (Where to Be Careful)

- Cutoff safety is enforced by `HistoryReader(..., strict_as_of=True)` in `repo_routing/inputs/builder.py`.
- Post-cutoff signals should not appear in feature extraction; new SQL queries should always include `<= cutoff` predicates.
- Pinned artifacts are anchored to `base_sha` (not repo HEAD) via `repo_routing.repo_profile.storage.pinned_artifact_path`.
- Boundary artifacts are anchored to `cutoff_key` via `repo_routing.boundary.paths`.
