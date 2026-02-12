# PR-01: Boundary Core and Artifact Foundation

## Purpose
Establish the boundary domain model and deterministic artifact contract without changing routing behavior yet.

## Scope
- New boundary schema/types.
- Deterministic serializer + hash contract.
- Boundary artifact paths and IO.
- Unit tests for schema invariants and determinism.

## Non-Goals
- No inference strategy implementation yet.
- No feature/risk/input cutover yet.
- No parser integration yet.

---

## Exact File-by-File Change List

## New files

1. `packages/inference/src/repo_routing/boundary/__init__.py`
   - Export canonical boundary APIs.

2. `packages/inference/src/repo_routing/boundary/models.py`
   - `Granularity`, `MembershipMode`, `BoundaryUnit`, `BoundaryDef`, `Membership`, `BoundaryModel`.
   - Invariant helpers for mode semantics.

3. `packages/inference/src/repo_routing/boundary/config.py`
   - `BoundaryConfig`, `BoundaryHashConfig`, `BoundaryDeterminismConfig`.

4. `packages/inference/src/repo_routing/boundary/hash.py`
   - Canonical payload builder.
   - Deterministic hash (`sha256`) over normalized payload.

5. `packages/inference/src/repo_routing/boundary/paths.py`
   - `repo_boundary_artifacts_dir(...)`
   - `boundary_model_dir(...)`
   - `boundary_model_path(...)`, `boundary_memberships_path(...)`, `boundary_manifest_path(...)`

6. `packages/inference/src/repo_routing/boundary/artifacts.py`
   - `BoundaryModelArtifact` and manifest metadata models.

7. `packages/inference/src/repo_routing/boundary/io.py`
   - deterministic read/write functions for boundary artifacts.

8. `packages/inference/tests/test_boundary_models.py`
   - schema validation and mode invariant tests.

9. `packages/inference/tests/test_boundary_hash.py`
   - deterministic hash reproducibility tests.

10. `packages/inference/tests/test_boundary_io.py`
   - artifact roundtrip tests and stable ordering checks.

11. `docs/attention-routing/boundary-model.md`
   - short contract doc for new boundary schema and artifact fields.

## Modified files

1. `packages/inference/src/repo_routing/paths.py`
   - Add helper paths for boundary artifacts (if centralized in shared path module).

2. `packages/inference/src/repo_routing/artifacts/__init__.py`
   - Export boundary artifact helpers (if colocated with existing artifact writer APIs).

3. `packages/inference/src/repo_routing/artifacts/paths.py`
   - Optional integration helpers if keeping boundary outputs alongside eval artifact utilities.

4. `packages/inference/src/repo_routing/__init__.py` (if present)
   - expose boundary package public surface.

## Deleted files
- None.

---

## Design Notes

- `BoundaryModel` is strategy-agnostic; it does not encode algorithm internals.
- Hash is computed after:
  - sorted lists/maps,
  - normalized floats,
  - canonical metadata ordering.
- Membership invariants are strict:
  - hard = exactly one membership per unit per granularity where coverage required,
  - mixed = normalized sums and explicit unknown handling.

---

## Tests / Validation

- Determinism tests:
  - same logical model with shuffled input ordering yields identical hash.
- Schema tests:
  - invalid memberships rejected with clear errors.
- IO tests:
  - write → read roundtrip preserves canonical content.

---

## Risks

- Over-constraining invariants too early.
  - Mitigation: keep config-driven strictness toggles in `BoundaryConfig`.

---

## Acceptance Criteria

- Boundary schemas compile and serialize deterministically.
- Hash contract stable across repeated runs.
- No runtime behavior changes in routing stack yet.
