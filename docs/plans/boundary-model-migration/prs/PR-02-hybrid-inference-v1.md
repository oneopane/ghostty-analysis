# PR-02: Hybrid Boundary Inference v1 (Path + Co-change)

## Purpose
Introduce the first production inference strategy (`hybrid_path_cochange.v1`) that builds deterministic boundary artifacts using existing DB data.

## Scope
- Strategy interface + strategy registry.
- Path and co-change signal extraction.
- Deterministic hard + mixed file-level memberships.
- CLI surface to build boundary artifacts.

## Non-Goals
- Parser signals.
- Runtime cutover to boundary consumers.

---

## Exact File-by-File Change List

## New files

1. `packages/inference/src/repo_routing/boundary/inference/__init__.py`
   - export strategy APIs and default strategy loader.

2. `packages/inference/src/repo_routing/boundary/inference/base.py`
   - `BoundaryInferenceContext`, `BoundaryInferenceStrategy` protocol.

3. `packages/inference/src/repo_routing/boundary/inference/registry.py`
   - strategy lookup by `strategy_id`.

4. `packages/inference/src/repo_routing/boundary/inference/hybrid_path_cochange_v1.py`
   - default inference implementation.

5. `packages/inference/src/repo_routing/boundary/signals/__init__.py`

6. `packages/inference/src/repo_routing/boundary/signals/path.py`
   - deterministic path-derived priors and directory normalization.

7. `packages/inference/src/repo_routing/boundary/signals/cochange.py`
   - co-change graph extraction from `pull_request_files` as-of cutoff.

8. `packages/inference/src/repo_routing/boundary/pipeline.py`
   - top-level API:
     - `build_boundary_model(...)`
     - `write_boundary_model_artifacts(...)`

9. `packages/inference/tests/test_boundary_inference_hybrid_v1.py`
   - correctness and deterministic clustering tests.

10. `packages/inference/tests/test_boundary_cutoff_safety.py`
   - as-of boundary enforcement tests.

11. `packages/inference/tests/test_boundary_cli_build.py`
   - CLI invocation and artifact output tests.

## Modified files

1. `packages/inference/src/repo_routing/cli/app.py`
   - add `boundary build` command group (or equivalent single command) with strategy/config flags.

2. `packages/inference/src/repo_routing/artifacts/writer.py`
   - optional integration helpers for writing boundary artifacts from CLI/eval workflows.

3. `packages/inference/src/repo_routing/artifacts/paths.py`
   - optional helper path functions if reusing existing path helper surface.

4. `packages/inference/src/repo_routing/time.py` (if needed)
   - utility for canonical cutoff formatting and watermark handling.

5. `packages/inference/tests/test_cli_app.py`
   - add command-level coverage for new boundary CLI command.

## Deleted files
- None.

---

## Inference Details

- Build unit universe from observed files before cutoff.
- Compute pairwise co-change scores from historical PR file sets.
- Combine path prior + co-change signal with fixed weights.
- Emit:
  - hard memberships (file partition),
  - mixed memberships (normalized distribution).
- Deterministic tie-breakers:
  - lexical file path order,
  - lexical boundary ID order,
  - stable floating-point rounding policy.

---

## Tests / Validation

- Deterministic rerun: same DB + cutoff + config => same model hash.
- Cutoff leak test: synthetic post-cutoff events must not alter output.
- Sparse repo test: emits minimal valid model with confidence diagnostics.

---

## Risks

- Co-change noise in low-volume repos.
  - Mitigation: confidence metadata + fallback partition behavior.

---

## Acceptance Criteria

- `hybrid_path_cochange.v1` artifacts produced deterministically.
- CLI can build model artifacts for selected repo/cutoff.
- No parser dependency required for v1 strategy.
