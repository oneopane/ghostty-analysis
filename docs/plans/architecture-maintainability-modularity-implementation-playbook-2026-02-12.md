# Architecture Maintainability & Modularity Implementation Playbook

Date: 2026-02-12  
Scope: `packages/ingestion`, `packages/inference`, `packages/evaluation`, `packages/experimentation`, `packages/cli`  
Audience: Engineers implementing architecture hardening work without prior repository context

## 1) Purpose and outcomes

This document is the single execution guide for architecture improvements focused on maintainability, modularity, and scalability while keeping feature delivery unblocked.

Target outcomes:

1. Stable package boundaries with explicit inter-package APIs.
2. Smaller, more cohesive orchestration modules.
3. Reduced cross-package coupling to internal modules.
4. Better scalability for evaluation and ingestion operations.
5. Enforced architecture rules via tests/CI, not only documentation.

## 2) Non-goals and constraints

Non-goals:

1. No rewrite of core domain logic.
2. No module/package renames for core import roots (`gh_history_ingestion`, `repo_routing`, `evaluation_harness`, `repo_cli`).
3. No breaking CLI contract changes unless explicitly called out in a migration step.

Constraints:

1. Preserve existing behavior first; refactor structure second.
2. Prefer additive APIs and phased migrations.
3. Keep each phase shippable independently.

## 3) Current architecture baseline (confirmed)

Primary evidence paths:

1. Workspace structure: `pyproject.toml`, `AGENTS.md`
2. CLI composition: `packages/cli/src/repo_cli/cli.py`
3. Evaluation orchestration: `packages/evaluation/src/evaluation_harness/runner.py`
4. Experiment orchestration: `packages/experimentation/src/experimentation/workflow_*.py`
5. Router contracts/spec parsing: `packages/inference/src/repo_routing/registry.py`, `packages/inference/src/repo_routing/router_specs.py`
6. Ingestion orchestration/checkpoints: `packages/ingestion/src/gh_history_ingestion/ingest/backfill.py`, `packages/ingestion/src/gh_history_ingestion/ingest/incremental.py`, `packages/ingestion/src/gh_history_ingestion/ingest/pipeline.py`
7. CI coverage: `.github/workflows/docs-checks.yml`

## 4) Execution model

Use this implementation model for every step:

1. Make the smallest change that creates the new boundary/capability.
2. Add or update tests in the owning package.
3. Run targeted package tests.
4. Run workspace regression tests.
5. Update docs/AGENTS to reflect actual architecture.

Definition of done per step:

1. Code merged with tests passing.
2. Boundary ownership is explicit in code and docs.
3. Migration path is documented if old path still exists.

## 5) Phased plan overview

Priority legend:

- `P0`: immediate maintainability risk reduction.
- `P1`: medium-term modularity/scalability improvements.
- `P2`: strategic hardening and cleanup.

Phases:

1. Phase A (`P0`): API boundaries + low-risk modularity cleanup.
2. Phase B (`P1`): orchestration decomposition + scalability primitives.
3. Phase C (`P2`): enforcement, cleanup, and long-tail migrations.

---

## 6) Detailed step-by-step implementation plan

## Phase A (P0): Boundary hardening and low-risk modular improvements

### Step A1: Establish explicit public API surface for `evaluation_harness`

Goal:

- Prevent external packages from importing `evaluation_harness` internals (especially `runner` internals).

Implementation:

1. Create `packages/evaluation/src/evaluation_harness/api.py`.
2. Export only stable public types/functions needed externally:
   - `run`, `show`, `list_runs`, `explain` from `service.py`
   - `EvalRunConfig`, `EvalDefaults` from `config.py`
   - `compute_run_id` from `run_id.py`
   - `RepoProfileRunSettings` as a stable contract type (move or re-export deliberately)
3. Add module docstring explicitly stating allowed imports for other packages.
4. Update `packages/experimentation/src/experimentation/workflow_*.py` to import from `evaluation_harness.api` only.

Files to modify:

1. `packages/evaluation/src/evaluation_harness/api.py` (new)
2. `packages/evaluation/src/evaluation_harness/__init__.py`
3. `packages/experimentation/src/experimentation/workflow_artifacts.py`
4. `packages/experimentation/src/experimentation/workflow_run.py`
5. Any other `packages/experimentation/src/experimentation/*.py` importing deep evaluation internals.

Tests:

1. Add test ensuring API module exposes expected symbols.
2. Update/migrate experimentation tests.

Validation commands:

```bash
uv run --project packages/evaluation pytest -q packages/evaluation/tests
uv run --project packages/experimentation pytest -q packages/experimentation/tests
```

Done criteria:

1. No `experimentation` import from `evaluation_harness.runner` remains.
2. Tests pass.

---

### Step A2: Enforce import-boundary rules with architecture tests

Goal:

- Make package boundary rules executable.

Implementation:

1. Add `packages/cli/tests/test_architecture_import_boundaries.py` or repository-level architecture test suite.
2. Parse Python files and fail on forbidden import patterns.
3. Start with explicit rules:
   - `experimentation` may import `evaluation_harness.api` but not `evaluation_harness.runner`.
   - `cli` should not import deep internals from `evaluation_harness` and `repo_routing` unless through declared entry surfaces.
4. Include allowlist exceptions if needed, with comments and target removal dates.

Files to add/modify:

1. `packages/cli/tests/test_architecture_import_boundaries.py` (or `scripts/` + test wrapper)
2. `.github/workflows/docs-checks.yml` (ensure this test runs in CI)

Tests/validation:

```bash
uv run --all-packages pytest -q
```

Done criteria:

1. Boundary test exists and is required in CI.
2. Current architecture rules are encoded and passing.

---

### Step A3: Centralize runtime defaults shared across CLIs

Goal:

- Remove duplicated defaults and reduce drift.

Implementation:

1. Add shared module in inference/evaluation boundary-safe location, e.g.:
   - `packages/inference/src/repo_routing/runtime_defaults.py`
   - or create small new shared package if needed (prefer not in first pass).
2. Define constants/options for:
   - default `data_dir`
   - default `top_k`
   - common time parsing helpers where already shared (`parse_dt_utc`)
3. Update CLIs:
   - `packages/ingestion/src/gh_history_ingestion/cli/app.py`
   - `packages/inference/src/repo_routing/cli/app.py`
   - `packages/evaluation/src/evaluation_harness/cli/app.py`
   - `packages/experimentation/src/experimentation/workflow_run.py`

Files to modify:

1. New runtime defaults module
2. CLI files above

Done criteria:

1. Defaults are single-sourced for core runtime constants.
2. CLI behavior unchanged (tests pass).

---

### Step A4: Bring package AGENTS/docs in sync with current module structure

Goal:

- Fix architecture documentation drift and onboarding confusion.

Implementation:

1. Update `packages/experimentation/AGENTS.md` to list current `workflow_*` modules.
2. Update `packages/cli/AGENTS.md` to document degraded command group behavior.
3. Update any stale references in `docs/architecture-brief.md` and `docs/README.md`.

Files to modify:

1. `packages/experimentation/AGENTS.md`
2. `packages/cli/AGENTS.md`
3. `docs/architecture-brief.md`
4. `docs/README.md`

Validation:

```bash
uv run python scripts/validate_docs_naming.py
```

Done criteria:

1. Docs reflect actual code structure.
2. No stale module claims remain for moved responsibilities.

---

## Phase B (P1): Cohesion and scalability improvements

### Step B1: Decompose evaluation runner into stage modules with stable contracts

Goal:

- Reduce maintenance risk in `runner.py` while preserving behavior.

Implementation:

1. Create stage modules:
   - `packages/evaluation/src/evaluation_harness/runner_prepare.py`
   - `packages/evaluation/src/evaluation_harness/runner_per_pr.py`
   - `packages/evaluation/src/evaluation_harness/runner_aggregate.py`
   - `packages/evaluation/src/evaluation_harness/runner_emit.py`
2. Move corresponding logic from `runner.py` incrementally.
3. Keep `run_streaming_eval(...)` in `runner.py` as orchestrator wrapper to preserve import compatibility.
4. Ensure shared dataclasses (prepared/per-pr/aggregate stage payloads) are in one module (`runner_models.py` if needed).

Files to modify:

1. `packages/evaluation/src/evaluation_harness/runner.py`
2. New runner stage modules above
3. Related imports in tests

Tests:

1. Preserve all existing evaluation tests.
2. Add focused unit tests per stage module if absent.

Validation:

```bash
uv run --project packages/evaluation pytest -q packages/evaluation/tests
```

Done criteria:

1. `runner.py` is orchestration-focused and substantially smaller.
2. No behavior regression in end-to-end eval tests.

---

### Step B2: Introduce optional parallel evaluation execution mode

Goal:

- Improve scaling for large PR/router sets.

Implementation:

1. Add config flag in `EvalDefaults` / `EvalRunConfig`:
   - `execution_mode: "sequential" | "parallel"` (default `sequential`)
   - optional `max_workers`.
2. Implement router execution concurrency per PR first (lowest risk), preserving deterministic output order in artifacts.
3. Keep output serialization deterministic by sorting router ids before writes.
4. Guard with feature flag; do not switch default in first release.

Files to modify:

1. `packages/evaluation/src/evaluation_harness/config.py`
2. `packages/evaluation/src/evaluation_harness/runner_per_pr.py` (or equivalent)
3. `packages/evaluation/src/evaluation_harness/cli/app.py` for flags

Tests:

1. New tests asserting identical report outputs between sequential and parallel modes for fixture DB.
2. Race-safety tests for artifact writing path.

Validation:

```bash
uv run --project packages/evaluation pytest -q packages/evaluation/tests
```

Done criteria:

1. Parallel mode exists and passes deterministic equivalence tests.
2. Default remains sequential until confidence threshold is reached.

---

### Step B3: Persist ingestion checkpoints for resumable operations

Goal:

- Improve long-run reliability and restartability for ingestion.

Implementation:

1. Extend schema with checkpoint persistence table (for example `ingestion_checkpoints`).
2. Wire `IngestStagePipeline.checkpoint(...)` to optional DB write.
3. Add resume option to ingestion commands (start from next incomplete stage).
4. Keep default behavior unchanged if resume flag is not provided.

Files to modify:

1. `packages/ingestion/src/gh_history_ingestion/storage/schema.py`
2. `packages/ingestion/src/gh_history_ingestion/storage/upsert.py`
3. `packages/ingestion/src/gh_history_ingestion/ingest/pipeline.py`
4. `packages/ingestion/src/gh_history_ingestion/ingest/backfill.py`
5. `packages/ingestion/src/gh_history_ingestion/ingest/incremental.py`
6. `packages/ingestion/src/gh_history_ingestion/cli/app.py`

Tests:

1. Checkpoint persistence tests.
2. Resume flow tests for interrupted backfill/incremental runs.

Validation:

```bash
uv run --project packages/ingestion pytest -q packages/ingestion/tests
```

Done criteria:

1. Checkpoints are persisted and queryable.
2. Resume mode successfully continues from persisted checkpoints.

---

### Step B4: Narrow cross-package access to inference internals from experimentation

Goal:

- Improve cohesion by depending on explicit inference entry APIs.

Implementation:

1. Create `packages/inference/src/repo_routing/api.py` exposing stable accessors used by experimentation.
2. Migrate `experimentation` imports from deep internals (history/profile/storage helper internals) to `repo_routing.api` where possible.
3. Keep deep imports only where absolutely required and document TODO deprecations.

Files to modify:

1. `packages/inference/src/repo_routing/api.py` (new)
2. `packages/experimentation/src/experimentation/workflow_helpers.py`
3. `packages/experimentation/src/experimentation/workflow_artifacts.py`
4. `packages/experimentation/src/experimentation/workflow_profile.py`

Done criteria:

1. Deep internal imports reduced to documented exceptions.
2. Public API pattern is established for inference package.

---

## Phase C (P2): Strategic cleanup and hardening

### Step C1: Deprecate and remove compatibility shims with explicit schedule

Goal:

- Eliminate long-term alias debt.

Implementation:

1. Inventory shims:
   - `packages/cli/src/repo_cli/unified_experiment.py`
   - `packages/cli/src/repo_cli/marimo_components.py`
   - `packages/ingestion/src/gh_history_ingestion/github/client.py`
   - `packages/ingestion/src/gh_history_ingestion/github/auth.py`
2. Add deprecation notices in docstrings with target removal release/date.
3. Update internal imports/tests to canonical module paths.
4. Remove shims once no import references remain.

Done criteria:

1. Shim usage is measurable and reaches zero before deletion.
2. Canonical import paths are documented and enforced by tests.

---

### Step C2: Re-root unified CLI on dedicated composition app

Goal:

- Make CLI composition ownership explicit and independent.

Implementation:

1. Replace root assignment from ingestion app with dedicated Typer root in `repo_cli`.
2. Mount ingestion under `repo ingestion ...` command group.
3. Add compatibility aliases only if required, with clear migration messaging.

Files to modify:

1. `packages/cli/src/repo_cli/cli.py`
2. CLI tests under `packages/cli/tests`
3. Usage docs in `packages/cli/README.md` and `docs/examples/*`

Done criteria:

1. `repo` root app is owned by `repo_cli` and composes subcommands explicitly.
2. CLI docs/tests match updated command tree.

---

### Step C3: Add CODEOWNERS-aligned ownership map for architectural modules

Goal:

- Ensure clear stewardship and review routing for high-change architecture files.

Implementation:

1. Create ownership map section in docs (or `docs/architecture-brief.md`).
2. Align with `.github/CODEOWNERS` if present; add/update if absent.
3. Ensure critical modules have explicit owners:
   - evaluation runner stages
   - experimentation workflows
   - inference registry/router specs
   - ingestion pipeline

Done criteria:

1. Ownership map exists and is enforceable via PR review workflows.

---

## 7) Validation checklist per phase

## Phase A validation

1. `uv run --project packages/evaluation pytest -q packages/evaluation/tests`
2. `uv run --project packages/experimentation pytest -q packages/experimentation/tests`
3. `uv run --project packages/cli pytest -q packages/cli/tests`
4. `uv run python scripts/validate_docs_naming.py`

## Phase B validation

1. `uv run --project packages/evaluation pytest -q packages/evaluation/tests`
2. `uv run --project packages/ingestion pytest -q packages/ingestion/tests`
3. Determinism comparison tests between sequential/parallel eval modes.

## Phase C validation

1. Full workspace tests:

```bash
uv run --all-packages pytest -q
```

2. CLI smoke:

```bash
uv run --project packages/cli repo --help
uv run --project packages/ingestion ingestion --help
uv run --project packages/inference inference --help
uv run --project packages/evaluation evaluation --help
```

## 8) Rollout strategy (no feature freeze)

1. Use short-lived branches per step.
2. Keep each step mergeable and test-complete.
3. Merge Phase A first; allow feature work to continue.
4. For Phase B concurrency/resume changes, ship behind flags first.
5. Remove deprecated paths only after two successful release cycles (or agreed equivalent).

## 9) Risk management

Top risks and controls:

1. Refactor regressions in evaluation:
   - Control: stage-by-stage extraction with unchanged external API + fixture-based end-to-end tests.
2. Hidden coupling breaks during API tightening:
   - Control: architecture import tests + temporary compatibility re-exports.
3. Parallel evaluation nondeterminism:
   - Control: deterministic write ordering + exact output equivalence tests.
4. Ingestion resume complexity:
   - Control: add persistence first, resume second, with explicit fallback to full run.

## 10) Implementation sequence summary (recommended order)

1. A1 API surface for evaluation.
2. A2 import-boundary architecture tests.
3. A3 shared runtime defaults.
4. A4 docs/AGENTS sync.
5. B1 evaluation runner decomposition.
6. B2 optional parallel eval mode.
7. B3 persistent ingestion checkpoints + resume.
8. B4 inference API surface for experimentation.
9. C1 compatibility shim deprecation/removal.
10. C2 CLI re-root cleanup.
11. C3 ownership map + CODEOWNERS alignment.

## 11) Acceptance checklist (program-level)

Use this to decide if the architecture program is complete:

- [ ] `experimentation` depends on `evaluation_harness.api` instead of evaluation internals.
- [ ] Architecture boundary tests exist and are mandatory in CI.
- [ ] Evaluation orchestration is modularized into cohesive stage modules.
- [ ] Optional parallel evaluation mode is implemented and deterministically validated.
- [ ] Ingestion checkpoints are persisted and resumable.
- [ ] Inference exposes a stable API surface for external package use.
- [ ] Compatibility shims are either removed or on explicit dated deprecation path.
- [ ] Unified CLI composition ownership is explicit in `repo_cli`.
- [ ] AGENTS/docs accurately reflect real module layout and ownership.
- [ ] Workspace test and smoke suite remains green.

