# PR-05: Mixed-Membership Migration (Area Basis → Boundary Basis)

## Purpose
Replace area-basis mixed-membership dataset/modeling with boundary-basis equivalents.

## Scope
- Rename/restructure mixed-membership basis package.
- Build user×boundary activity rows.
- Adapt NMF artifact fields and feature derivation to boundary terms.

## Non-Goals
- New model families beyond NMF.
- Parser-specific boundary signals (already integrated through boundary model artifacts).

---

## Exact File-by-File Change List

## New files

1. `packages/inference/src/repo_routing/mixed_membership/boundaries/__init__.py`

2. `packages/inference/src/repo_routing/mixed_membership/boundaries/basis.py`
   - boundary distribution from PR file set via boundary projection.
   - user×boundary activity row builder.
   - rows→matrix conversion.

3. `packages/inference/tests/test_mixed_membership_boundary_api.py`
   - replacement coverage for prior area API tests.

## Modified files

1. `packages/inference/src/repo_routing/mixed_membership/config.py`
   - rename versions:
     - `mm.areas.nmf.v1` → `mm.boundary.nmf.v1`
     - basis version default to boundary strategy version.
   - rename config fields referencing “area”.

2. `packages/inference/src/repo_routing/mixed_membership/artifacts.py`
   - rename artifact fields:
     - `areas` → `boundaries`
     - `role_area_mix` → `role_boundary_mix`
   - update deterministic hash payload keys.

3. `packages/inference/src/repo_routing/mixed_membership/dataset.py`
   - source from boundary basis builders.

4. `packages/inference/src/repo_routing/mixed_membership/pipeline.py`
   - derive PR boundary distribution instead of area distribution.
   - candidate and pair feature derivation renamed accordingly.

5. `packages/inference/src/repo_routing/mixed_membership/models/nmf.py`
   - matrix axis names and projection logic boundary-native.
   - output feature key names updated to boundary equivalents.

6. `packages/inference/src/repo_routing/mixed_membership/models/__init__.py`
   - exports update.

7. `packages/inference/src/repo_routing/mixed_membership/__init__.py`
   - public API updates.

8. `packages/inference/tests/test_mixed_membership_api.py`
   - migrate or replace with boundary assertions.

9. `experiments/marimo/mixed_membership_areas_v0.py`
   - either replaced or updated to boundary-named notebook/app.

10. `docs/attention-routing/mixed-membership.md`
    - boundary-basis narrative and API examples.

## Deleted files

1. `packages/inference/src/repo_routing/mixed_membership/areas/__init__.py`
2. `packages/inference/src/repo_routing/mixed_membership/areas/basis.py`
3. `experiments/marimo/mixed_membership_areas_v0.py` (if replaced by new filename)

(If notebook renamed, add new file `experiments/marimo/mixed_membership_boundaries_v1.py`.)

---

## Migration Notes

- Preserve deterministic matrix ordering and model hashing behavior.
- Keep model family and numerical behavior stable where possible; naming and basis semantics change.
- Candidate/pair feature naming in mixed-membership should align with PR-04 conventions.

---

## Tests / Validation

- deterministic row and matrix generation,
- NMF fit reproducibility checks,
- candidate/pair feature generation for boundary basis.

---

## Risks

- artifact schema break for previously persisted mixed-membership models.
  - Mitigation: explicit version bump and migration note (no compatibility promise).

---

## Acceptance Criteria

- mixed-membership lane no longer imports area basis code,
- boundary-basis artifact + features generated deterministically,
- updated notebook/demo path documented.
