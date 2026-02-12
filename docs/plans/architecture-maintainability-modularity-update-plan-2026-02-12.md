# Architecture Maintainability & Modularity Update Plan (2026-02-12)

Date: 2026-02-12  
Scope: `packages/ingestion`, `packages/inference`, `packages/evaluation`, `packages/experimentation`, `packages/cli`

## Purpose
This document turns the architecture review into a single ordered execution plan focused on maintainability and modularity improvements without halting feature delivery.

## Progress Update (2026-02-12)

Status: implementation pass complete for all planned items in this report.

Completed scope highlights:

- P0 CLI operability:
  - `packages/cli/src/repo_cli/cli.py` now mounts degraded command groups with explicit load-failure reasons instead of silently dropping groups.
- P0 CI coverage:
  - `.github/workflows/docs-checks.yml` expanded to workspace checks with docs validation, per-package smoke checks, and per-package tests.
- P0 report parity:
  - Experiment post-processing now updates `report.json` and writes a synchronized post-processing block into `report.md` (`packages/experimentation/src/experimentation/workflow_quality.py`).
- P0 shared router parsing:
  - New reusable router spec parser/validator in inference (`packages/inference/src/repo_routing/router_specs.py`) reused from inference/evaluation/experimentation command flows.
- P0 test ownership:
  - Added package-local experimentation suite (`packages/experimentation/tests/test_unified_experiment_workflows.py`) and narrowed CLI test scope (`packages/cli/tests/test_unified_experiment_cli.py`).
- P1 package boundary cleanup:
  - Added evaluation service APIs (`packages/evaluation/src/evaluation_harness/service.py`) and switched experimentation to use these APIs instead of evaluation CLI command imports.
- P1 experimentation modularization:
  - Split monolith into focused modules:
    - `workflow_cohort.py`
    - `workflow_spec.py`
    - `workflow_run.py`
    - `workflow_quality.py`
    - `workflow_diff.py`
    - `workflow_doctor.py`
    - `workflow_profile.py`
    - shared `workflow_helpers.py`
  - `packages/experimentation/src/experimentation/unified_experiment.py` is now a thin command assembly/export layer.
- P1 evaluation runner staging:
  - `packages/evaluation/src/evaluation_harness/runner.py` now uses typed stage handoffs:
    - `_prepare_eval_stage`
    - `_per_pr_evaluate_stage`
    - `_aggregate_eval_stage`
    - `_emit_eval_stage`
- P1 ingestion staging/checkpoints:
  - Added `packages/ingestion/src/gh_history_ingestion/ingest/pipeline.py` and integrated stage checkpoints in backfill/incremental orchestration.
- P2 router config validation:
  - Builtin router config validation now explicit for `hybrid_ranker`, `llm_rerank`, and `stewards` in `packages/inference/src/repo_routing/registry.py`.
- P2 registry extensibility:
  - Boundary strategy/parser registries now use registration maps/hooks instead of hardcoded `if/elif` branching.
- P2 dependency/docs hygiene:
  - Moved ingestion test dependencies to optional dev extras (`packages/ingestion/pyproject.toml`).
  - `scripts/validate_feature_stack.sh` now supports `.venv/bin/pytest` or `uv run --all-packages pytest` fallback.
  - Updated architecture/docs alignment in:
    - `docs/attention-routing/README.md`
    - `docs/architecture-brief.md`

Validation run during this pass:

- `python3 -m compileall -q packages/cli/src packages/evaluation/src packages/experimentation/src packages/inference/src packages/ingestion/src`
- `.venv/bin/pytest -q packages/inference/tests/test_registry_loading.py packages/inference/tests/test_registry_config_validation.py packages/inference/tests/test_boundary_parser_registry.py packages/inference/tests/test_boundary_registry_hooks.py packages/evaluation/tests/test_cli_validation.py packages/experimentation/tests/test_unified_experiment_workflows.py packages/cli/tests/test_unified_experiment_cli.py`
- `.venv/bin/pytest -q packages/evaluation/tests/test_runner_router_specs.py packages/evaluation/tests/test_runner_import_router.py packages/evaluation/tests/test_end_to_end_run.py packages/evaluation/tests/test_runner_repo_profile.py packages/evaluation/tests/test_leakage_guards.py`
- `.venv/bin/pytest -q packages/ingestion/tests/test_backfill.py packages/ingestion/tests/test_incremental.py`

## Continuation Update (2026-02-12, post-compaction)

Status: continuation hardening pass complete; no cross-package regressions detected.

Additional modularity updates completed:

- Experimentation helper decomposition continued:
  - Added `packages/experimentation/src/experimentation/workflow_artifacts.py` for:
    - artifact presence checks
    - artifact prefetch orchestration
    - prefetch summary construction
    - repo-profile settings construction
  - Added `packages/experimentation/src/experimentation/workflow_reports.py` for:
    - experiment manifest payload construction
    - run-context loading
    - report/per-PR loading
    - numeric delta rendering
- Updated command modules to import focused helper modules directly:
  - `packages/experimentation/src/experimentation/workflow_run.py`
  - `packages/experimentation/src/experimentation/workflow_profile.py`
  - `packages/experimentation/src/experimentation/workflow_diff.py`
  - `packages/experimentation/src/experimentation/unified_experiment.py`
- Reduced `packages/experimentation/src/experimentation/workflow_helpers.py` from 585 lines to 383 lines while preserving existing behavior and compatibility exports.

Validation run during this continuation:

- `python3 -m compileall -q packages/experimentation/src packages/cli/src`
- `.venv/bin/pytest -q packages/experimentation/tests/test_unified_experiment_workflows.py packages/cli/tests/test_unified_experiment_cli.py`
  - Result: `12 passed`
- `uv run --all-packages pytest -q`
  - Result: `157 passed, 1 skipped`

## Confirmed Strengths To Preserve
- Clear workspace package boundaries and mostly one-way dependency flow.
- Deterministic artifact/report serialization patterns.
- Strong cutoff/leakage safety model in inference and evaluation flows.
- Rich architecture and process documentation with explicit traceability.

## Confirmed Observations Vs Assumptions
- Confirmed observations are based on current source and docs:
  - `pyproject.toml`
  - `packages/*/pyproject.toml`
  - `packages/*/src/**`
  - `docs/attention-routing/**`
  - `docs/plans/evaluation-harness/**`
- Assumption:
  - `.github/workflows/docs-checks.yml` is the primary in-repo CI configuration; if external CI exists, CI-related risk severity is lower.

## Ordered Execution Plan

1. P0: Make unified CLI failure states explicit.
   - Action: Replace silent `except Exception: pass` in `packages/cli/src/repo_cli/cli.py` with explicit degraded-mode warnings that identify the missing/broken package and why command groups are unavailable.
   - Why: Hidden command loss is a high-risk operability and debugging issue.
   - Effort: S
   - Risk: Low
   - Expected Benefit: Immediate observability of cross-package wiring failures.
   - Suggested Owner: CLI package owner
   - Primary Evidence: `packages/cli/src/repo_cli/cli.py`

2. P0: Add full package CI (not docs-only).
   - Action: Extend CI workflows to run package tests and smoke checks for all workspace packages in addition to docs validation.
   - Why: Coupled monorepo changes currently lack automated architecture-level safeguards in visible workflow config.
   - Effort: M
   - Risk: Low
   - Expected Benefit: Prevents cross-package regressions from merging silently.
   - Suggested Owner: DevEx/Infra
   - Primary Evidence: `.github/workflows/docs-checks.yml`

3. P0: Eliminate report dual-truth drift.
   - Action: Ensure post-run experiment quality/promotion updates cannot mutate `report.json` without preserving semantic parity with `report.md`.
   - Why: Two report formats that can diverge create downstream confusion and reduce trust in outputs.
   - Effort: S
   - Risk: Low
   - Expected Benefit: Single reliable reporting contract.
   - Suggested Owner: Evaluation + Experimentation owners
   - Primary Evidence: `packages/evaluation/src/evaluation_harness/runner.py`, `packages/experimentation/src/experimentation/unified_experiment.py`

4. P0: Centralize router spec parsing/validation.
   - Action: Move router list/config parsing and validation into a shared reusable module in inference; reuse from inference/evaluation/experimentation CLIs.
   - Why: Current duplication invites behavior drift and inconsistent user-facing semantics.
   - Effort: M
   - Risk: Low
   - Expected Benefit: One canonical routing config contract.
   - Suggested Owner: Inference owner
   - Primary Evidence: `packages/inference/src/repo_routing/cli/app.py`, `packages/evaluation/src/evaluation_harness/cli/app.py`, `packages/experimentation/src/experimentation/unified_experiment.py`

5. P0: Create package-local experimentation tests and narrow CLI test scope.
   - Action: Add `packages/experimentation/tests` for orchestration logic; keep `packages/cli/tests` focused on CLI wiring and integration.
   - Why: Experimentation behavior is currently tested mostly through CLI-level tests and shims, which blurs ownership.
   - Effort: M
   - Risk: Low
   - Expected Benefit: Better modular testability and clearer maintenance boundaries.
   - Suggested Owner: Experimentation owner
   - Primary Evidence: `packages/cli/tests/test_unified_experiment_cli.py`, `packages/cli/src/repo_cli/unified_experiment.py`

6. P1: Introduce evaluation service APIs and stop importing evaluation CLI command functions.
   - Action: Add service-level APIs in evaluation (`run`, `show`, `list`, `explain`) and make experimentation call those APIs instead of Typer command functions.
   - Why: CLI-layer imports across packages create avoidable coupling and fragile layering.
   - Effort: M
   - Risk: Medium
   - Expected Benefit: Cleaner package boundaries and safer refactors.
   - Suggested Owner: Evaluation owner
   - Primary Evidence: `packages/experimentation/src/experimentation/unified_experiment.py`

7. P1: Split `unified_experiment.py` by responsibility.
   - Action: Decompose into focused modules such as `cohort`, `spec`, `run`, `quality`, `diff`, `profile`, and shared helpers.
   - Why: The file is a high-change orchestration hotspot with mixed concerns.
   - Effort: L
   - Risk: Medium
   - Expected Benefit: Higher cohesion, lower change blast radius, easier onboarding.
   - Suggested Owner: Experimentation owner
   - Primary Evidence: `packages/experimentation/src/experimentation/unified_experiment.py`

8. P1: Decompose evaluation runner into explicit pipeline stages.
   - Action: Split `run_streaming_eval` into stage functions with typed handoff models (`prepare`, `per_pr_evaluate`, `aggregate`, `emit`).
   - Why: Current single-flow orchestration mixes routing execution, truth logic, aggregation, and file emission.
   - Effort: L
   - Risk: Medium
   - Expected Benefit: Better unit-testability and future scalability options.
   - Suggested Owner: Evaluation owner
   - Primary Evidence: `packages/evaluation/src/evaluation_harness/runner.py`

9. P1: Refactor ingestion orchestration into explicit stage/checkpoint pipeline.
   - Action: Keep existing behavior but introduce staged orchestration and checkpoint semantics across backfill and incremental flows.
   - Why: Ingestion logic is large and transactionally fragmented, making recovery and evolution harder.
   - Effort: L
   - Risk: Medium
   - Expected Benefit: Improved maintainability and operational robustness on larger repos.
   - Suggested Owner: Ingestion owner
   - Primary Evidence: `packages/ingestion/src/gh_history_ingestion/ingest/backfill.py`, `packages/ingestion/src/gh_history_ingestion/ingest/incremental.py`

10. P2: Add schema validation for builtin router configuration files.
    - Action: Validate `hybrid_ranker`, `llm_rerank`, and `stewards` config payloads with explicit models before router instantiation.
    - Why: Current JSON reads are permissive and can fail late at runtime.
    - Effort: M
    - Risk: Low
    - Expected Benefit: Early, clear failure modes and safer extension.
    - Suggested Owner: Inference owner
    - Primary Evidence: `packages/inference/src/repo_routing/registry.py`

11. P2: Convert hardcoded boundary/parser registry branching to registration maps or plugin hooks.
    - Action: Replace `if/elif` strategy/backend branching with explicit registries that are easier to extend safely.
    - Why: Hardcoded selection paths create repetitive edits and scaling friction.
    - Effort: M
    - Risk: Medium
    - Expected Benefit: Better extensibility with lower change risk.
    - Suggested Owner: Inference owner
    - Primary Evidence: `packages/inference/src/repo_routing/boundary/inference/registry.py`, `packages/inference/src/repo_routing/boundary/parsers/registry.py`

12. P2: Clean dependency/tooling hygiene and reduce docs drift.
    - Action: Move test-only dependencies out of runtime where appropriate, align validation workflows, and reconcile stale/high-level architecture docs with current code.
    - Why: Inconsistent packaging and stale architecture narratives increase maintenance overhead.
    - Effort: S-M
    - Risk: Low
    - Expected Benefit: Lower onboarding friction and fewer environment/documentation mismatches.
    - Suggested Owner: Ingestion + Docs owners
    - Primary Evidence: `packages/ingestion/pyproject.toml`, `scripts/validate_feature_stack.sh`, `docs/attention-routing/README.md`, `docs/architecture-brief.md`

## Sequencing Rules
- Complete steps 1-5 before starting major module splits.
- Complete step 6 before step 7 to avoid refactoring on unstable cross-package boundaries.
- Step 8 can start after step 6 begins, but should merge before step 11 to avoid compounding extension complexity.
- Step 9 should run in parallel only with P2 work, not with step 1-4, to keep high-risk churn isolated.

## Completion Checklist
- [x] CLI surfaces never disappear silently; degraded modes are explicitly reported.
- [x] CI runs package tests for all workspace packages on pull requests.
- [x] Router parsing and config validation are centralized and reused.
- [x] Experimentation has package-local tests for core orchestration logic.
- [x] Experimentation no longer imports evaluation CLI command functions.
- [x] Evaluation runner is split into composable stages with typed boundaries.
- [x] Ingestion orchestration has explicit stage/checkpoint semantics.
- [x] Report outputs remain semantically consistent after experiment post-processing.
- [x] Boundary/parser registry extension no longer requires branching edits.
- [x] Runtime dependencies and docs are aligned with actual architecture behavior.
