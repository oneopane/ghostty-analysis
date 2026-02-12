# PR-04: Predictor Feature Stack Migration to Boundary Keys

## Purpose
Migrate feature extraction, registry, and task-policy surfaces from area-centric keys to boundary-centric keys.

## Scope
- PR/candidate/pair features using boundary signals.
- Feature registry key updates.
- Task policy prefix updates.
- Feature extractor debug/source metadata updates.

## Non-Goals
- Parser backend implementation (PR-06/07).
- Mixed-membership module changes (PR-05).

---

## Exact File-by-File Change List

## New files

1. `packages/inference/src/repo_routing/predictor/features/boundary_utils.py`
   - shared helpers for footprint normalization, entropy, overlap, sparse dot products.

2. `packages/inference/tests/test_boundary_feature_registry_keys.py`
   - ensures expected boundary key coverage is present and classified.

## Modified files

1. `packages/inference/src/repo_routing/predictor/feature_extractor_v1.py`
   - remove area overrides source hash logic.
   - include boundary artifact/model hash metadata.
   - ensure outputs emit `pr.boundary.*` and related interaction features.

2. `packages/inference/src/repo_routing/predictor/features/pr_surface.py`
   - replace `pr.areas.*` keys with `pr.boundary.*` equivalents.

3. `packages/inference/src/repo_routing/predictor/features/candidate_activity.py`
   - replace area footprint derivations with boundary footprint derivations.

4. `packages/inference/src/repo_routing/predictor/features/interaction.py`
   - area overlap and area-dot-product interaction keys replaced by boundary-based variants.

5. `packages/inference/src/repo_routing/predictor/features/similarity.py`
   - nearest PR common-area features replaced by common-boundary features.

6. `packages/inference/src/repo_routing/predictor/features/repo_priors.py`
   - area frequency priors replaced by boundary frequency priors.

7. `packages/inference/src/repo_routing/predictor/features/ownership.py`
   - area override hit-rate logic removed/replaced with boundary coverage/consistency checks.

8. `packages/inference/src/repo_routing/predictor/features/feature_registry.py`
   - remove registrations under `pr.areas.*`, area-specific pair keys.
   - add `pr.boundary.*`, `pair.affinity.boundary_*`, and boundary similarity key registrations.

9. `packages/inference/src/repo_routing/predictor/features/task_policy.py`
   - update allowed prefixes from `pr.areas.` to `pr.boundary.` and related boundary prefix families.

10. `packages/inference/src/repo_routing/predictor/features/feature_roadmap` files (if any in code/docs)
    - update key examples and references.

11. `packages/inference/tests/test_feature_registry.py`
    - update expected registry lookups.

12. `packages/inference/tests/test_feature_roadmap_v1_keys.py`
    - update expected key presence.

13. `packages/inference/tests/test_pr_surface_features.py`
    - update key assertions.

14. `packages/inference/tests/test_repo_priors_similarity_automation.py`
    - update input fixture fields and output key assertions.

15. `packages/inference/tests/test_task_policy_registry.py`
    - policy allow/deny tests updated for boundary prefixes.

16. `packages/inference/tests/test_candidate_activity_features.py`
    - boundary footprint metric assertions.

17. `packages/inference/tests/test_feature_extractor_v1.py`
    - update expected extracted keys and debug source hashes.

## Deleted files
- None required (unless area-specific helper modules become dead and are removed in this PR).

---

## Key Migration Policy

- No long-lived alias keys.
- Feature names migrate directly.
- Task policy docs and tests updated in same PR to avoid split-brain behavior.

---

## Tests / Validation

- feature registry coverage remains complete,
- task policies evaluate against new boundary keys,
- end-to-end extractor smoke tests pass with deterministic output.

---

## Risks

- Broad key churn can break downstream notebooks/scripts.
  - Mitigation: explicit migration notes in docs and one-time breaking change.

---

## Acceptance Criteria

- No extractor output contains `pr.areas.*` keys.
- Boundary key families are fully registered/policy-validated.
- Predictor tests pass with updated fixtures.
