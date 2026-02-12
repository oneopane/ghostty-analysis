# PR-03: Inputs, Analysis, and Risk Cutover to Boundary

## Purpose
Switch core runtime consumers from area semantics to boundary semantics.

## Scope
- `PRInputBundle` boundary footprint fields.
- Input builder boundary projection.
- Analysis engine overlap logic on boundaries.
- Risk logic keyed on boundary coverage.
- Route receipt/evidence terminology updates.

## Non-Goals
- Predictor feature-stack key migration (handled in PR-04).
- Mixed-membership migration (handled in PR-05).

---

## Exact File-by-File Change List

## New files

1. `packages/inference/src/repo_routing/boundary/consumption/__init__.py`

2. `packages/inference/src/repo_routing/boundary/consumption/projection.py`
   - project file list into boundary footprint for a PR snapshot.

3. `packages/inference/src/repo_routing/boundary/consumption/models.py`
   - `PRBoundaryFootprint`, `BoundaryCoverageSummary`.

4. `packages/inference/tests/test_boundary_projection.py`
   - projection determinism and coverage tests.

## Modified files

1. `packages/inference/src/repo_routing/inputs/models.py`
   - replace/remove:
     - `file_areas`, `areas`
   - add:
     - `file_boundaries`, `boundaries`, mixed footprint fields, boundary metadata.

2. `packages/inference/src/repo_routing/inputs/builder.py`
   - remove `area_for_path` mapping path.
   - load boundary model artifact and project changed files to boundary footprint.

3. `packages/inference/src/repo_routing/analysis/models.py`
   - rename/replace fields:
     - `area_overlap_activity` → boundary overlap feature(s)
     - `areas` → boundary set/summary.

4. `packages/inference/src/repo_routing/analysis/engine.py`
   - replace current/event overlap computation with boundary overlap computation.
   - evidence payload renamed to boundary terms.

5. `packages/inference/src/repo_routing/scoring/config.py`
   - rename feature weight keys to boundary equivalents.

6. `packages/inference/src/repo_routing/scoring/risk.py`
   - `areas` input replaced by boundary coverage input.

7. `packages/inference/src/repo_routing/policy/labels.py`
   - `routed-area:*` labels replaced with boundary label policy (e.g., `routed-boundary:*`).

8. `packages/inference/src/repo_routing/receipt/render.py`
   - text output updated for boundary terminology and overlap fields.

9. `packages/inference/src/repo_routing/router/base.py` (if needed)
   - optional metadata extension for boundary summary in route outputs.

10. `packages/inference/src/repo_routing/artifacts/models.py`
    - artifact schema fields reflecting boundary footprint in input/snapshot contexts as needed.

11. `packages/inference/src/repo_routing/artifacts/writer.py`
    - ensure input artifacts serialize new boundary fields.

12. `packages/inference/src/repo_routing/examples/llm_router_example.py`
    - consume boundary fields instead of area fields.

13. `packages/inference/tests/test_inputs_bundle.py`
    - update expected schema and values.

14. `packages/inference/tests/test_scoring.py`
    - risk expectations updated to boundary inputs.

15. `packages/inference/tests/test_receipt.py`
    - output expectations updated.

16. `packages/inference/tests/test_labels.py`
    - label output update assertions.

17. `packages/inference/tests/test_stewards_router.py`
    - overlap field and score key updates.

## Deleted files

1. `packages/inference/src/repo_routing/exports/area.py`
   - remove legacy area mapping API from active codebase.

2. `packages/inference/tests/test_exports_area.py`
   - remove area-specific tests (replaced by boundary tests).

---

## Migration Notes

- This PR intentionally changes runtime schema names; callers/tests are updated in-place.
- No compatibility alias layer is introduced.
- If boundary artifact unavailable, failure mode must be explicit and deterministic (configurable strict/lenient mode).

---

## Tests / Validation

- input artifact determinism with boundary fields,
- analysis overlap behavior parity check (semantic parity, renamed keys),
- risk assignment tests for missing boundary coverage.

---

## Risks

- Wide rename surface can break hidden consumers.
  - Mitigation: repo-wide key search/update + strict tests.

---

## Acceptance Criteria

- Input/analysis/risk layers no longer depend on area functions or area fields.
- Route evidence/labels/receipts boundary-native.
- All affected tests updated and passing.
