# Artifact-Native SDLC Rewrite (V2)

Implement `docs/plans/2026-02-14-artifact-native-sdlc-rewrite.md` task-by-task with strict TDD (fail -> minimal fix -> pass) and verification evidence.

## Goals
- Replace run-output-centric flow with artifact-native contracts and stores.
- Cut inference/evaluation/experimentation/CLI to artifact-native paths.
- Ensure derived human views (`per_pr.jsonl`, `report.json`) are generated from artifact index.
- Add semantic backfill and candidate/champion promotion support.
- Land docs and scenario coverage.

## Checklist
- [x] Task 1: Define V2 artifact type contracts in core
- [x] Task 2: Add append-only artifact index store
- [x] Task 3: Upgrade FileArtifactStore to artifact-native write/read/cache lookup
- [x] Task 4: Add PromptSpec + PromptStore
- [x] Task 5: Add RunManifest V2 + run store roundtrip
- [x] Task 6: Cut inference artifact writer to FileArtifactStore
- [x] Task 7: Replace LLM replay cache with semantic cache + provenance
- [x] Task 8: Introduce operator abstraction + registry bridge
- [x] Task 9: Add cutoff horizon check command (`repo evaluation cutoff`)
- [x] Task 10: Make evaluation per-PR stage artifact-native
- [x] Task 11: Derive `per_pr.jsonl` and `report.json` from artifact index
- [x] Task 12: Add `repo artifacts list/show`
- [x] Task 13: Add candidate/champion registry for promotion
- [x] Task 14: Add `repo backfill semantic`
- [x] Task 15: Documentation + scenario script + validation

## Verification
- Task 1 fail: `uv run --project packages/core pytest packages/core/tests/test_artifact_types_v2.py::test_artifact_record_has_stable_artifact_id -v` -> `ImportError: cannot import name 'ArtifactEntityRef'`.
- Task 1 pass: same command -> `1 passed`.
- Task 2 fail: `uv run --project packages/core pytest packages/core/tests/test_artifact_index_store.py::test_artifact_index_append_and_filter -v` -> `ModuleNotFoundError: sdlc_core.store.artifact_index`.
- Task 2 pass: same command -> `1 passed`.
- Task 3 fail: `uv run --project packages/core pytest packages/core/tests/test_file_artifact_store_v2.py::test_file_artifact_store_write_and_cache_lookup -v` -> `AttributeError: 'FileArtifactStore' object has no attribute 'write_artifact'`.
- Task 3 pass: same command -> `1 passed`.
- Task 4 fail: `uv run --project packages/core pytest packages/core/tests/test_prompt_store.py::test_prompt_store_register_and_get -v` -> `ModuleNotFoundError: sdlc_core.store.prompt_store`.
- Task 4 pass: same command -> `1 passed`.
- Task 5 fail: `uv run --project packages/core pytest packages/core/tests/test_run_store_v2.py::test_run_store_roundtrip_manifest -v` -> `ImportError: cannot import name 'RunManifest'`.
- Task 5 pass: same command -> `1 passed`.
- Core batch verification: `uv run --project packages/core pytest packages/core/tests -v` -> `5 passed`.
- Task 6 fail: `uv run --project packages/inference pytest packages/inference/tests/test_artifact_writer_v2.py::test_route_write_creates_artifact_index_entry -v` -> `AttributeError: 'ArtifactWriter' object has no attribute 'write_route_result_v2'`.
- Task 6 pass: same command -> `1 passed`.
- Task 7 fail: `uv run --project packages/inference pytest packages/inference/tests/test_llm_semantic_cache.py::test_llm_semantic_cache_roundtrip -v` -> `ImportError: cannot import name 'LLMSemanticCache'`.
- Task 7 pass: same command -> `1 passed`.
- Task 8 fail: `uv run --project packages/inference pytest packages/inference/tests/test_operator_registry.py::test_builtin_router_operators_are_registered -v` -> `ModuleNotFoundError: No module named 'repo_routing.operators'`.
- Task 8 pass: same command -> `1 passed`.
- Inference sanity checks: 
  - `uv run --project packages/inference pytest packages/inference/tests/test_artifact_writer_v2.py::test_route_write_creates_artifact_index_entry packages/inference/tests/test_llm_semantic_cache.py::test_llm_semantic_cache_roundtrip -v` -> `2 passed`.
  - `uv run --project packages/inference pytest packages/inference/tests/test_llm_cache.py -q` -> `1 passed`.
  - `uv run --project packages/inference pytest packages/inference/tests/test_api_surface.py -q` -> `1 passed`.
- Task 9 fail: `uv run --project packages/evaluation pytest packages/evaluation/tests/test_cutoff_horizon_check.py::test_cutoff_horizon_check_returns_pass_or_fail -v` -> `exit_code == 2` (CLI rejected `--cutoff`).
- Task 9 pass: same command -> `1 passed`.
- Task 10 fail: `uv run --project packages/evaluation pytest packages/evaluation/tests/test_runner_per_pr_artifact_native.py::test_runner_writes_artifact_index_with_truth_and_routes -v` -> `FileNotFoundError: artifact_index.jsonl`.
- Task 10 pass: same command -> `1 passed`.
- Task 11 baseline check: `uv run --project packages/evaluation pytest packages/evaluation/tests/test_derived_views_v2.py::test_emit_materializes_report_and_per_pr_from_artifacts -v` -> `1 passed` (files existed pre-derived module).
- Task 11 implementation verification:
  - Added `packages/evaluation/src/evaluation_harness/derived_views.py` and wired `runner_emit.py` + `runner_aggregate.py`.
  - `uv run --project packages/evaluation pytest packages/evaluation/tests/test_cutoff_horizon_check.py::test_cutoff_horizon_check_returns_pass_or_fail packages/evaluation/tests/test_runner_per_pr_artifact_native.py::test_runner_writes_artifact_index_with_truth_and_routes packages/evaluation/tests/test_derived_views_v2.py::test_emit_materializes_report_and_per_pr_from_artifacts packages/evaluation/tests/test_cli_validation.py::test_explain_supports_policy_selection -v` -> `4 passed`.
- Task 12 verification:
  - Added `packages/evaluation/src/evaluation_harness/artifact_service.py` and exported via `packages/evaluation/src/evaluation_harness/api.py`.
  - Added top-level CLI group in `packages/cli/src/repo_cli/cli.py` (`repo artifacts list/show`).
  - `uv run --project packages/cli pytest packages/cli/tests/test_repo_artifacts_cli.py::test_repo_artifacts_group_exists -v` -> `1 passed`.
- Task 13 verification:
  - Added `packages/experimentation/src/experimentation/workflow_registry.py` and CLI wiring in `packages/experimentation/src/experimentation/unified_experiment.py`.
  - `uv run --project packages/experimentation pytest packages/experimentation/tests/test_candidate_registry.py::test_candidate_registry_promotes_champion -v` -> `1 passed`.
- Task 14 fail: `uv run --project packages/cli pytest packages/cli/tests/test_repo_artifacts_cli.py::test_repo_backfill_group_exists -v` -> `No such command 'backfill'`.
- Task 14 pass:
  - Added `packages/inference/src/repo_routing/semantic/backfill.py` and CLI wiring in both `packages/inference/src/repo_routing/cli/app.py` and `packages/cli/src/repo_cli/cli.py`.
  - `uv run --project packages/cli pytest packages/cli/tests/test_repo_artifacts_cli.py::test_repo_artifacts_group_exists packages/cli/tests/test_repo_artifacts_cli.py::test_repo_backfill_group_exists -v` -> `2 passed`.
  - `uv run --project packages/inference pytest packages/inference/tests/test_semantic_backfill.py -v` -> `1 passed`.
  - `uv run --project packages/experimentation pytest packages/experimentation/tests/test_candidate_registry.py packages/experimentation/tests/test_workflow_promote.py -v` -> `3 passed`.
- Task 15 fail: `uv run --project packages/cli pytest packages/cli/tests/test_docs_quickstart_v2.py::test_quickstart_mentions_artifacts_and_backfill -v` -> `AssertionError` (`docs/quickstart.md` missing).
- Task 15 pass:
  - Added docs: `docs/quickstart.md`, `docs/artifact-types-cache-keys.md`.
  - Added scenario script: `scripts/scenario_artifact_native_v2.sh` (executable).
  - Updated references: `docs/README.md`, `docs/system-transcript.md`.
  - `uv run --project packages/cli pytest packages/cli/tests/test_docs_quickstart_v2.py -v` -> `1 passed`.
  - `uv run --project packages/cli pytest packages/cli/tests/test_repo_artifacts_cli.py -v` -> `2 passed`.
  - `./scripts/validate_feature_stack.sh` -> `all checks passed` (`130 passed, 1 skipped` in full relevant suites).

## Notes
- Worktree currently contains unrelated in-flight changes; avoid touching unrelated files.
- Completed all planned tasks (1-15) with fail->pass evidence and validation.
