# Executive Summary

This repository is a **Python `uv` workspace monorepo** for offline routing experiments over GitHub PR history, with a tight loop:

1) ingest GitHub data into SQLite,  
2) build cutoff-safe PR inputs/routes,  
3) run leakage-aware offline evaluation,  
4) emit reproducible artifacts/reports.

Core workspace members are defined in `pyproject.toml` and include:

- `packages/ingestion`
- `packages/inference`
- `packages/experimentation`
- `packages/evaluation`
- `packages/cli`

## 2026-02-12 Maintainability Update Snapshot

Recent architecture hardening changes reflected in code:

- Unified CLI now exposes explicit degraded-mode command groups when optional package wiring fails (`packages/cli/src/repo_cli/cli.py`).
- Router option parsing/validation is centralized in inference and reused by other CLIs (`packages/inference/src/repo_routing/router_specs.py`).
- Evaluation now exposes a stable package API surface (`evaluation_harness.api`) used by experimentation (`packages/evaluation/src/evaluation_harness/api.py`).
- Experimentation workflow code is split into focused modules (`workflow_cohort.py`, `workflow_spec.py`, `workflow_run.py`, `workflow_quality.py`, `workflow_diff.py`, `workflow_doctor.py`, `workflow_profile.py`).
- Experiment post-processing writes synchronized `report.json` and `report.md` updates to prevent report drift (`packages/experimentation/src/experimentation/workflow_quality.py`).
- Boundary strategy/parser registries now support registration maps/hooks rather than hardcoded branching (`packages/inference/src/repo_routing/boundary/*/registry.py`).

**Start here for no-code execution:**

- [`examples/e2e-unified-cli.md`](./examples/e2e-unified-cli.md) (canonical end-to-end workflow)
- [`examples/README.md`](./examples/README.md) (artifact strategy)

Key architecture properties already implemented:

- **Deterministic, local-first data substrate** (`data/github/<owner>/<repo>/history.sqlite`) (`packages/inference/src/repo_routing/paths.py`, `packages/evaluation/src/evaluation_harness/paths.py`).
- **As-of cutoff reads** for PR state via interval tables (`packages/inference/src/repo_routing/history/reader.py`, `packages/ingestion/src/gh_history_ingestion/intervals/rebuild.py`).
- **Strict streaming eval guardrail** (fail loud if cutoff exceeds DB event horizon in strict mode) (`packages/evaluation/src/evaluation_harness/runner.py`, `packages/evaluation/tests/test_leakage_guards.py`).
- **Router plugin model** (builtin + import-path) (`packages/inference/src/repo_routing/registry.py`).

Recently completed work is reflected in docs/code:

- 001 changed-files signal implemented (`pull_request_files`) (`docs/plans/evaluation-harness/001-add-pr-changed-files-signal.md`, `packages/ingestion/src/gh_history_ingestion/storage/schema.py`).
- 002 truth-signal ingestion effectively implemented (`pull-requests --with-truth`) (`docs/plans/evaluation-harness/002-ensure-truth-signals.md`, `packages/ingestion/src/gh_history_ingestion/ingest/pull_requests.py`).
- 024 leakage guardrail tests implemented (`docs/plans/evaluation-harness/024-tests-guardrails.md`, `packages/evaluation/tests/test_leakage_guards.py`).
- 026/027 docs implemented (`packages/evaluation/docs/runbook.md`, `packages/evaluation/docs/metrics.md`, `packages/evaluation/docs/baselines.md`).

**Critical caveat (still open):** evaluation currently does **not** clearly separate:
- “true no post-cutoff response” vs
- “truth missing due to ingestion gaps,”  
even though ingestion gaps are tracked (`ingestion_gaps`, `qa_reports`) (`packages/ingestion/src/gh_history_ingestion/storage/schema.py`, `packages/ingestion/src/gh_history_ingestion/ingest/qa.py`).

---

# Repository Map

## Workspace and package wiring

- Workspace members: `pyproject.toml`
- Script entrypoints:
  - `ingestion = gh_history_ingestion.cli.app:app` (`packages/ingestion/pyproject.toml`)
  - `inference = repo_routing.cli.app:app` (`packages/inference/pyproject.toml`)
  - `evaluation = evaluation_harness.cli.app:app` (`packages/evaluation/pyproject.toml`)
  - `repo = repo_cli.cli:app` (`packages/cli/pyproject.toml`)
- Experiment workflow internals live in `packages/experimentation` and are mounted into the `repo` CLI.

## High-level directory layout

- `packages/` → code packages (src-layout) (`AGENTS.md`)
- `experiments/` → reproducible experiment configs/extract scripts/marimo notebooks
- `notebooks/` → exploratory marimo notebooks and demos
- `docs/attention-routing/` → current architecture + feature policy docs (`docs/attention-routing/README.md`)
- `docs/plans/evaluation-harness/` → atomic implementation plan/checklist (`docs/plans/evaluation-harness/README.md`)
- `scripts/` → validation/quality scripts (`scripts/validate_feature_stack.sh`, `scripts/check_feature_quality.py`)
- `data/` → local SQLite + eval artifacts (`AGENTS.md`)

## Package dependency graph (code deps + data deps)

```text
cli
 ├─ ingestion
 ├─ inference
 ├─ evaluation
 └─ experimentation

experimentation
 ├─ ingestion
 ├─ inference
 └─ evaluation

evaluation ──(python dependency)──> inference

Data dependency:
ingestion ──writes──> data/github/<owner>/<repo>/history.sqlite
inference + evaluation ──read──> same history.sqlite
evaluation + inference ──write──> data/github/<owner>/<repo>/eval/<run_id>/
```

- Python dependency evidence: `evaluation` depends on `inference` (`packages/evaluation/pyproject.toml`).
- `inference` is explicitly offline/local data only (`packages/inference/README.md`).

---

# Package-by-Package Architecture

## 1) `packages/ingestion` (GitHub → SQLite canonical history)

**Entry CLI:** `packages/ingestion/src/gh_history_ingestion/cli/app.py`

### Main command surfaces
- `ingest` (full backfill): calls `backfill_repo(...)` (`.../ingest/backfill.py`)
- `incremental`: calls `incremental_update(...)` (`.../ingest/incremental.py`)
- `pull_requests`: PR-window backfill; `--with-truth` optionally ingests reviews/comments/issue-events for eval readiness (`.../ingest/pull_requests.py`)
- `explore`: local read-only SQLite explorer (`.../explorer/server.py`)

### Storage model + upserts
- Schema definitions: `packages/ingestion/src/gh_history_ingestion/storage/schema.py`
- Upsert primitives: `.../storage/upsert.py`
  - includes `upsert_pull_request_file`, `upsert_review`, `upsert_comment`, `insert_event`, `upsert_watermark`, `insert_gap`.
- Changed-files table exists: `pull_request_files` with composite key and indexes (`.../storage/schema.py`).

### Temporal/as-of infrastructure
- Raw events normalized and inserted (`.../events/normalizers/*.py`, `.../storage/upsert.py`).
- Interval rebuild generates as-of tables (`.../intervals/rebuild.py`), including:
  - `pull_request_head_intervals`
  - `pull_request_review_request_intervals`
  - `pull_request_draft_intervals`
  - issue/comment/review interval tables.

### Data quality tracking
- Pagination anomalies tracked in `ingestion_gaps` via `GapRecorder` (`.../ingest/qa.py`).
- Aggregated QA summaries in `qa_reports` (`.../ingest/qa.py`).

---

## 2) `packages/inference` (offline PR inputs + routers + artifacts)

**Entry CLI:** `packages/inference/src/repo_routing/cli/app.py`

### Core responsibilities
- **As-of PR snapshots:** `HistoryReader.pull_request_snapshot(...)` (`.../history/reader.py`)
- **Canonical PR input bundle:** `build_pr_input_bundle(...)` (`.../inputs/builder.py`, `.../inputs/models.py`)
- **Router contracts:** `RouteResult`, `RouteCandidate`, `Evidence` (`.../router/base.py`)
- **Builtin routers:** mentions/popularity/codeowners/stewards (`.../router/baselines/*.py`, `.../router/stewards.py`)
- **Router registry/plugins:** builtin + import-path (`.../registry.py`)
- **Artifact writing:** deterministic JSON for snapshots/routes/features (`.../artifacts/writer.py`, `.../artifacts/paths.py`)

### Builtin baselines (implemented behavior)
- `mentions`: parses @mentions from PR text (`.../router/baselines/mentions.py`)
- `popularity`: recent reviewer/commenter activity (`.../router/baselines/popularity.py`)
- `codeowners`: pinned CODEOWNERS at `base_sha` path; high-risk empty if missing (`.../router/baselines/codeowners.py`)
- `stewards`: scoring-based analysis using config (`.../analysis/engine.py`, `.../scoring/config.py`)

### Feature-science scaffolding (present)
- Feature extractor v1 and feature family modules (`.../predictor/feature_extractor_v1.py`, `.../predictor/features/*.py`)
- Feature registry + task policy metadata (`.../predictor/features/feature_registry.py`, `.../predictor/features/task_policy.py`)
- Pipeline predictor + optional JSON cache (`.../predictor/pipeline.py`)
- Mixed-membership exploration lane (`.../mixed_membership/*`, `docs/attention-routing/mixed-membership.md`)

---

## 3) `packages/evaluation` (streaming eval + metrics + reports)

**Entry CLI:** `packages/evaluation/src/evaluation_harness/cli/app.py`

### Main command surfaces
- `run`, `sample`, `cutoff`, `show`, `list`, `explain` (`.../cli/app.py`)

### Core run orchestration
- `run_streaming_eval(...)` (`.../runner.py`)
  - computes cutoffs,
  - sorts PRs in streaming order by `(cutoff, pr_number)`,
  - writes per-PR artifacts,
  - computes truth + metrics,
  - writes report + manifest + per_pr JSONL.

### Truth + metrics
- Behavior truth extraction: `behavior_truth_first_eligible_review(...)` (`.../truth.py`)
- Routing agreement metrics: hit@1/3/5 + MRR (`.../metrics/routing_agreement.py`)
- Gate correlation: parse PR gate fields + merge signal (`.../metrics/gates.py`)
- Queue metrics: TTFR(+optional TTFC) by risk bucket (`.../metrics/queue.py`)

### Reporting
- Output models: `EvalReport`, manifest model (`.../reporting/models.py`, `.../manifest.py`)
- Renderers: markdown/json formatting (`.../reporting/markdown.py`, `.../store/filesystem.py`)
- Run IDs: timestamp + config hash (`.../run_id.py`)

---

## 4) `packages/experimentation` (cohort/spec workflows + gates)

- Cohort/spec lifecycle, experiment run orchestration, quality gates, promotion checks, doctor/profile flows (`packages/experimentation/src/experimentation/unified_experiment.py`).
- Reusable marimo workflow components (`packages/experimentation/src/experimentation/marimo_components.py`).

## 5) `packages/cli` (unified command surface)

- Owns a dedicated `repo` root app and mounts `ingestion`, `cohort`, `experiment`, `profile`, `doctor`, plus optional `inference`/`evaluation` groups (`packages/cli/src/repo_cli/cli.py`).

---

# End-to-End Data Lifecycle

```text
GitHub REST API
   │
   ▼
ingestion (backfill/incremental/pull_requests --with-truth)
   ├─ upsert raw entities + events
   ├─ rebuild interval tables
   ├─ update watermarks
   └─ track ingestion_gaps + qa_reports
   ▼
data/github/<owner>/<repo>/history.sqlite
   │
   ├─ inference HistoryReader (strict as-of snapshots)
   ├─ inference inputs.builder (PRInputBundle)
   ├─ builtin/import routers -> RouteResult
   └─ deterministic artifacts under eval/<run_id>/prs/<pr>/*
   ▼
evaluation runner
   ├─ cutoff_for_pr
   ├─ behavior truth extraction
   ├─ per-router metrics
   ├─ per_pr.jsonl
   └─ report.json/report.md + manifest.json
```

## Data contract summary (table-level + artifact-level)

| Contract | Producer | Consumer | Key fields | Source path |
|---|---|---|---|---|
| `repos`, `users`, `pull_requests`, `issues` | ingestion upserts | routing/eval queries | repo identity, PR number/author/timestamps | `packages/ingestion/src/gh_history_ingestion/storage/schema.py`, `.../storage/upsert.py` |
| `events` | ingestion normalizers | intervals + eval merge-as-of checks | `occurred_at`, `event_type`, subject/object IDs | `.../events/normalizers/*.py`, `.../storage/upsert.py` |
| Interval tables (`pull_request_head_intervals`, `pull_request_review_request_intervals`, etc.) | `rebuild_intervals(...)` | `HistoryReader`, cutoff logic | start/end event IDs for as-of state | `.../intervals/rebuild.py`, `packages/inference/src/repo_routing/history/reader.py` |
| `pull_request_files` | PR file ingest | snapshots/features/baselines | path/churn keyed by PR+head_sha | `.../ingest/pull_request_files.py`, `.../storage/schema.py` |
| `reviews`, `comments` | ingestion | truth + queue + features | post-cutoff responses, activity history | `.../storage/schema.py`, `packages/evaluation/src/evaluation_harness/truth.py` |
| `watermarks` | ingestion | strict stale-cutoff guard | endpoint freshness markers | `.../storage/upsert.py`, `packages/evaluation/src/evaluation_harness/db.py` |
| `ingestion_gaps`, `qa_reports` | ingestion QA | (currently mostly manual) | pagination anomaly evidence | `.../ingest/qa.py`, `.../storage/schema.py` |
| `PRInputBundle` JSON | routing input builder | import-path predictors/rankers | canonical per-PR@cutoff feature input | `packages/inference/src/repo_routing/inputs/models.py` |
| `RouteArtifact` JSON | router execution | eval explanation/reporting | candidates/evidence/risk/confidence | `packages/inference/src/repo_routing/artifacts/models.py` |
| Eval outputs (`per_pr.jsonl`, `report.json/md`, `manifest.json`) | evaluation runner | user analysis + reproducibility | metrics summaries + run metadata | `packages/evaluation/src/evaluation_harness/runner.py` |

---

# Evaluation System Design

## Execution model

`run_streaming_eval(...)` orchestrates a strict offline pass (`packages/evaluation/src/evaluation_harness/runner.py`):

1. normalize routers (`RouterSpec`) and load routers (`repo_routing.registry`)
2. compute cutoffs per PR (`.../cutoff.py`)
3. sort PRs by `(cutoff, pr_number)` for streaming order
4. for each PR:
   - build/write snapshot + inputs artifacts (`repo_routing.artifacts.writer`)
   - compute behavior truth (`.../truth.py`)
   - compute gate metrics (`.../metrics/gates.py`)
   - run each router and score routing+queue metrics
   - append row to `per_pr.jsonl`
5. aggregate and emit:
   - `report.json`, `report.md`
   - `manifest.json`

## Cutoff and leakage rules

- Default cutoff policy is `created_at` (`.../config.py`).
- Supported policies in code: `created_at`, `created_at+<delta>`, `ready_for_review` (`.../cutoff.py`).
- Strict mode default `strict_streaming_eval=True` aborts stale-cutoff runs (`.../config.py`, `.../runner.py`).

## Truth and metric definitions (implemented)

- Behavior truth = first eligible post-cutoff review response in window (default 48h) with bot/author exclusions (`.../truth.py`, `packages/evaluation/docs/metrics.md`).
- Routing metrics: hit@1/3/5 and MRR (`.../metrics/routing_agreement.py`).
- Queue metrics: TTFR; TTFC is supported by function but currently not enabled in main runner call (`include_ttfc=False`) (`.../metrics/queue.py`, `.../runner.py`).
- Gate correlation from parsed PR body fields + merged-as-of signal (`.../metrics/gates.py`).

## Compatibility behavior

Per-PR output writes `routers` only (`.../runner_per_pr.py`).

---

# Guardrails, Leakage Risks, and Data Quality

## Implemented guardrails

- **As-of strictness:** `HistoryReader` enforces interval-based as-of state; missing interval rows can fail in strict mode (`packages/inference/src/repo_routing/history/reader.py`).
- **Strict stale-cutoff guard:** runtime abort when cutoff > max ingested event timestamp in strict mode (`packages/evaluation/src/evaluation_harness/runner.py`).
- **Deterministic output writes:** sorted JSON keys and stable ordering in artifacts/reports (`packages/inference/src/repo_routing/artifacts/writer.py`, `packages/evaluation/src/evaluation_harness/reporting/formatters.py`).
- **Bot/author filtering in truth/queue:** (`packages/evaluation/src/evaluation_harness/truth.py`, `.../metrics/queue.py`).
- **CODEOWNERS leakage warning + pinned path requirement:** (`packages/evaluation/docs/baselines.md`, `packages/inference/src/repo_routing/router/baselines/codeowners.py`).

## Risk matrix

| Risk | Type | Current control | Residual gap | Suggested mitigation |
|---|---|---|---|---|
| Cutoff leakage from stale DB | Leakage | strict stale-cutoff fail-loud (`runner.py`) | CLI currently does not expose strict toggle/cutoff controls directly | Add `--strict/--no-strict`, `--cutoff-policy` in eval CLI |
| CODEOWNERS future leakage | Leakage | pinned base SHA path loader (`codeowners.py`) + docs warning (`baselines.md`) | Missing pinned file silently degrades to empty/high-risk | Add preflight “coverage report” for CODEOWNERS presence before run |
| **No-response vs missing-truth ambiguity** | Data quality | `ingestion_gaps` + `qa_reports` tracked (`ingest/qa.py`) | Eval truth currently collapses to `None` with no cause label (`truth.py`, `runner.py`) | Implement truth-coverage diagnostics (detailed below) |
| Feature drift / unclassified features | Data quality | feature registry + task-policy metadata (`feature_registry.py`, `task_policy.py`) | Not currently enforced as hard eval gate | Add strict mode in `scripts/check_feature_quality.py --strict` to experiment checklist |
| Docs/code drift | Operational | architecture doc marks current vs historical docs (`docs/attention-routing/README.md`) | Some plan/task docs are stale/inconsistent | Add docs validation checklist per release |

## Concrete implementation approach for the truth-coverage gap

### Problem
Current eval treats “no truth found” as a single state (`truth_login is None`), so metrics cannot distinguish:
- real no-response PRs, vs
- potentially missing truth because ingestion is incomplete.

### Non-breaking implementation (recommended first)
1. Add a diagnostics model in `packages/evaluation/src/evaluation_harness/models.py`:
   - `truth_status: observed | no_post_cutoff_response | unknown_due_to_ingestion_gap`
   - counts: eligible reviews/comments scanned
   - supporting fields: truth window bounds, gap resources flagged.
2. Add `behavior_truth_with_diagnostics(...)` in `packages/evaluation/src/evaluation_harness/truth.py`:
   - retain existing selection logic,
   - additionally query `ingestion_gaps`/latest `qa_reports` for relevant resources.
3. In `run_streaming_eval(...)` (`.../runner.py`):
   - write both existing `truth_behavior` and new `truth_diagnostics` into `per_pr.jsonl`.
4. Extend report schema/rendering (`.../reporting/models.py`, `.../reporting/markdown.py`) with:
   - `truth_coverage_counts` by status.
5. Add tests:
   - `unknown_due_to_ingestion_gap` classification when gaps exist,
   - denominator-aware reporting.

### Optional schema extension (higher confidence diagnostics)
**Assumption/Needs verification:** current `ingestion_gaps` does not encode precise event-time coverage windows.  
Add `ingestion_coverage` table in ingestion package to record per-resource covered time windows and completeness status; then classify truth coverage by PR cutoff+truth window overlap.

---

# Current Status: Completed vs Outstanding

## Completed (with evidence)

| Item | Status | Evidence |
|---|---|---|
| 001 PR changed-files signal | Complete | `pull_request_files` schema/upsert/ingest path implemented (`packages/ingestion/src/gh_history_ingestion/storage/schema.py`, `.../storage/upsert.py`, `.../ingest/pull_request_files.py`), plus tests (`packages/ingestion/tests/test_pull_request_files.py`) |
| 002 Truth-signal ingestion flow | Effectively implemented | PR-window path supports `--with-truth` and ingests issue-events/comments/reviews/review-comments (`packages/ingestion/src/gh_history_ingestion/ingest/pull_requests.py`), documented in README (`packages/ingestion/README.md`) |
| 024 Strict leakage guardrail | Complete/hardened | strict stale-cutoff runtime error + test coverage (`packages/evaluation/src/evaluation_harness/runner.py`, `packages/evaluation/tests/test_leakage_guards.py`) |
| 026 Runbook + metric definitions | Complete | `packages/evaluation/docs/runbook.md`, `packages/evaluation/docs/metrics.md` |
| 027 Baseline limitations + CODEOWNERS leakage warning | Complete | `packages/evaluation/docs/baselines.md` |

## Outstanding / partially addressed

| Area | Current state | Why it matters | Evidence |
|---|---|---|---|
| Truth coverage disambiguation | Not implemented in eval outputs | Metrics conflates true no-response with missing data | `packages/evaluation/src/evaluation_harness/truth.py`, `.../runner.py`, `packages/ingestion/src/gh_history_ingestion/ingest/qa.py` |
| Intent truth in eval reporting | Function exists, runner does not use it | Leaves planned “intent vs behavior” split underutilized | `packages/evaluation/src/evaluation_harness/truth.py` (`intent_truth_from_review_requests`), `.../runner.py` |
| Eval CLI configurability | Run CLI lacks explicit strict/cutoff/ttfc knobs | Harder exploratory sweeps without code-level config changes | `packages/evaluation/src/evaluation_harness/cli/app.py`, `.../config.py` |
| TTFC metric usage | Implemented functionally, disabled in runner | Queue diagnostics less complete | `packages/evaluation/src/evaluation_harness/metrics/queue.py`, `.../runner.py` |
| CODEOWNERS artifact provisioning | **Assumption/Needs verification:** no automated ingestion path found in reviewed files | `codeowners` baseline quality depends on pinned file availability | `packages/inference/src/repo_routing/router/baselines/codeowners.py` |
| Docs consistency | Some planning docs appear stale | Can mislead future implementation decisions | `docs/plans/evaluation-harness/011-truth-extraction.md` (unchecked), `docs/plans/evaluation-harness/README.md` (index checked) |

---

# Experimentation Workflow (for DS iteration)

Below is a practical, rigorous loop using current tooling.

## A) One-time setup
- [ ] Create env + install workspace:
  - `uv venv`
  - `uv sync`
- [ ] Keep validation scripts available:
  - `scripts/validate_feature_stack.sh`
  - `scripts/check_feature_quality.py`

## B) Build/refresh local substrate
- [ ] Full ingest (recommended):
  - `uv run --project packages/ingestion ingestion ingest --repo <owner>/<repo>`
  - `uv run --project packages/ingestion ingestion incremental --repo <owner>/<repo>`
- [ ] Or PR-window ingest with truth:
  - `uv run --project packages/ingestion ingestion pull-requests --repo <owner>/<repo> --start-at <iso> --end-at <iso> --with-truth`

## C) Freeze cohort before modeling
- [ ] Sample PRs deterministically:
  - `uv run --project packages/evaluation evaluation sample --repo <owner>/<repo> --from <iso> --end-at <iso> --limit <n>`
- [ ] Save sampled PR list externally (single source for all router comparisons).

## D) Run baseline references first
- [ ] Run baseline pack on frozen cohort:
  - `uv run --project packages/evaluation evaluation run --repo <owner>/<repo> --pr ... --router mentions --router popularity --router codeowners`
- [ ] (Optional) add stewards with config:
  - `--router stewards --router-config <path/to/config.json>`

## E) Run experiment router(s) on exact same cohort
- [ ] Import-path experimental router:
  - `--router-import pkg.mod:Factory --router-config ...`
- [ ] Keep one variable change per run (feature set, ranker weights, or candidate generation).

## F) Analyze and sanity-check
- [ ] Inspect report:
  - `evaluation show --repo ... --run-id ...`
- [ ] Spot-check hard PRs:
  - `evaluation explain --repo ... --run-id ... --pr <n> --router <id>`
- [ ] Validate feature-policy quality:
  - `python scripts/check_feature_quality.py --run-dir data/github/<owner>/<repo>/eval/<run_id>`

## G) Reproducibility protocol (important)
- [ ] Archive `manifest.json`, `report.json`, `per_pr.jsonl`, router config, and hypothesis note.
- [ ] Re-run same config/cohort to confirm deterministic parity.
- [ ] Only promote changes that beat at least one non-ML baseline (`docs/attention-routing/tasks/README.md`).

---

# Architecture Strengths, Weaknesses, and Trade-offs

## Strengths
- Clear package boundaries and responsibilities (ingest vs routing vs eval).
- Strong temporal/as-of modeling via interval tables.
- Deterministic artifact and run metadata pipeline.
- Router extensibility via `RouterSpec` import paths.
- Existing feature taxonomy/policy scaffolding is unusually strong for experimentation.

## Weaknesses
- Truth coverage ambiguity (critical analysis blind spot).
- Some eval config fields are not fully exercised in CLI pipeline.
- Operational dependency on external/pinned artifacts (CODEOWNERS) without explicit readiness checks.
- Documentation consistency drift in some planning files.

## Trade-offs
- SQLite + deterministic offline design optimizes reproducibility and velocity, but limits scale/parallelism.
- Strict leakage controls reduce accidental optimism, but can block exploratory workflows unless toggles are exposed.
- Router-only terminology simplifies contracts but requires one-time migration for old consumers.

---

# Recommended Near-Term Roadmap (30/60/90 days)

**Roadmap tuning applied to your answers:** optimize for single-user velocity, include schema changes where useful, and pursue both reliability + new router scaffolding in parallel.

## 30 days (stabilize measurement integrity)
1. Implement truth coverage diagnostics and add status to `per_pr.jsonl` + report.
2. Add eval CLI flags for `--cutoff-policy`, `--strict/--no-strict`, and optional `--include-ttfc`.
3. Add preflight CODEOWNERS availability report for selected PR cohort.
4. Add a small “run diff” helper (compare two run_ids on same PR cohort).

## 60 days (speed up experimentation)
1. Create a canonical experimental import-path router scaffold using `feature_extractor_v1`.
2. Add ablation-friendly run templates (e.g., disable feature families by config).
3. Emit dual metrics: all PRs vs coverage-known PRs once truth diagnostics land.
4. **Optional schema change:** add `ingestion_coverage` windows for stronger missing-truth attribution.

## 90 days (deepen model iteration without breaking reproducibility)
1. Integrate mixed-membership-derived features into an experimental router lane.
2. Add notebook-driven analysis pack for:
   - per-risk bucket gains,
   - feature policy violations,
   - candidate-pool miss diagnostics.
3. Clean up docs drift and codify a “docs sync” checklist tied to release/test scripts.

## Prioritized backlog (effort/impact/confidence)

| Priority | Backlog item | Effort | Impact | Confidence |
|---|---:|---:|---:|---:|
| P0 | Truth coverage diagnostics (`observed/no_response/unknown_gap`) in eval outputs | M | Very High | High |
| P0 | Eval CLI flags: strict/cutoff/ttfc | S | High | High |
| P0 | Coverage-aware report denominators | M | High | Medium-High |
| P1 | CODEOWNERS preflight coverage audit | S | Medium-High | High |
| P1 | Experimental router scaffold (import-path + extractor v1 template) | M | High | High |
| P1 | Run comparison helper (`runA` vs `runB`) | S | Medium | High |
| P2 | Intent truth integration into report (secondary channel) | M | Medium | Medium |
| P2 | `ingestion_coverage` schema for precise completeness windows | L | High | Medium |
| P2 | Mixed-membership feature injection into experimental ranker | M-L | Medium-High | Medium |

---

# Appendix: Commands, Paths, and Key Symbols

## Core commands

- Unified CLI:
  - `uv run --project packages/cli repo --help`
- Ingestion:
  - `uv run --project packages/ingestion ingestion ingest --repo <owner>/<repo>`
  - `uv run --project packages/ingestion ingestion incremental --repo <owner>/<repo>`
  - `uv run --project packages/ingestion ingestion pull-requests --repo <owner>/<repo> --start-at <iso> --end-at <iso> --with-truth`
- Evaluation:
  - `uv run --project packages/evaluation evaluation run --repo <owner>/<repo> --pr ... --router mentions`
  - `uv run --project packages/evaluation evaluation show --repo <owner>/<repo> --run-id <run_id>`
  - `uv run --project packages/evaluation evaluation explain --repo <owner>/<repo> --run-id <run_id> --pr <n> --router <id>`
- Validation:
  - `./scripts/validate_feature_stack.sh`
  - `python scripts/check_feature_quality.py --run-dir data/github/<owner>/<repo>/eval/<run_id>`

## Key paths

- DB path: `data/github/<owner>/<repo>/history.sqlite`
- Eval run dir: `data/github/<owner>/<repo>/eval/<run_id>/`
- CODEOWNERS pinned path: `data/github/<owner>/<repo>/codeowners/<base_sha>/CODEOWNERS`
- Boundary artifact root: `data/github/<owner>/<repo>/artifacts/routing/boundary_model/`

## Key symbols (quick lookup)

| Symbol | Role | Path |
|---|---|---|
| `backfill_repo` | Full ingestion flow | `packages/ingestion/src/gh_history_ingestion/ingest/backfill.py` |
| `incremental_update` | Watermark-driven updates | `packages/ingestion/src/gh_history_ingestion/ingest/incremental.py` |
| `backfill_pull_requests` | PR-window ingest (+truth option) | `packages/ingestion/src/gh_history_ingestion/ingest/pull_requests.py` |
| `rebuild_intervals` | Build as-of interval tables | `packages/ingestion/src/gh_history_ingestion/intervals/rebuild.py` |
| `insert_event` / upserts | Canonical write primitives | `packages/ingestion/src/gh_history_ingestion/storage/upsert.py` |
| `HistoryReader.pull_request_snapshot` | As-of snapshot reads | `packages/inference/src/repo_routing/history/reader.py` |
| `build_pr_input_bundle` | Canonical model input | `packages/inference/src/repo_routing/inputs/builder.py` |
| `RouteResult` | Router output contract | `packages/inference/src/repo_routing/router/base.py` |
| `load_router` / `RouterSpec` | Router plugin loading | `packages/inference/src/repo_routing/registry.py` |
| `ArtifactWriter` | Deterministic artifact writes | `packages/inference/src/repo_routing/artifacts/writer.py` |
| `run_streaming_eval` | Main eval orchestration | `packages/evaluation/src/evaluation_harness/runner.py` |

## Architecture Ownership Map

| Module Area | Primary Owner |
|---|---|
| Evaluation runner orchestration/stages (`packages/evaluation/src/evaluation_harness/runner*.py`) | @oneopane |
| Experimentation workflows (`packages/experimentation/src/experimentation/workflow_*.py`) | @oneopane |
| Inference router registry/specs (`packages/inference/src/repo_routing/registry.py`, `packages/inference/src/repo_routing/router_specs.py`) | @oneopane |
| Ingestion orchestration pipeline (`packages/ingestion/src/gh_history_ingestion/ingest/*.py`) | @oneopane |
| `behavior_truth_first_eligible_review` | Behavior truth extraction | `packages/evaluation/src/evaluation_harness/truth.py` |
| `per_pr_metrics` | Routing metrics | `packages/evaluation/src/evaluation_harness/metrics/routing_agreement.py` |
| `per_pr_gate_metrics` | Gate metrics | `packages/evaluation/src/evaluation_harness/metrics/gates.py` |
| `per_pr_queue_metrics` | Queue timing metrics | `packages/evaluation/src/evaluation_harness/metrics/queue.py` |
| `render_report_md` | Human-readable report | `packages/evaluation/src/evaluation_harness/reporting/markdown.py` |

---

# Appendix: Open Questions for Next Design Review

1. Should coverage-aware routing metrics **exclude** `unknown_due_to_ingestion_gap` rows by default, or report dual denominators only?
2. Do you want truth diagnostics to remain non-breaking (`truth_behavior` preserved) for older notebook/report consumers?
3. Should `intent_truth_from_review_requests(...)` become first-class in run outputs now, or wait until behavior coverage diagnostics are complete?
4. Should strict mode toggles be exposed in CLI now, or intentionally kept Python-only to avoid accidental misuse?
5. Do you want automatic CODEOWNERS artifact readiness checks to hard-fail runs or just warn?
6. Is adding `ingestion_coverage` worth the schema complexity now, or should we start with `ingestion_gaps` heuristics only?
7. Should there be a first-party “experimental router template” command/file generator for faster iteration?
8. Do you want a minimal “run compare” utility in `evaluation` CLI (e.g., `compare --run-a --run-b`)?
9. **Assumption/Needs verification:** Is doc drift cleanup (e.g., stale task checkboxes) important enough to include in near-term milestones?
10. **Assumption/Needs verification:** Should mixed-membership stay notebook-only for now, or become an optional feature family in the main extractor path?
