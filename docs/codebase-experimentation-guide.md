# Ghostty Analysis Codebase Guide: Architecture, Experimentation, and How to Extend It

This document is a single, practical guide to the repository so you can:

1. understand how the system works end-to-end,
2. run experiments reproducibly,
3. and start writing new experiment code (routers, features, truth policies, profile logic).

## Start here (no-code end-to-end path)

If your goal is to complete the full CLI workflow without reading source code, use:

- [`examples/e2e-unified-cli.md`](./examples/e2e-unified-cli.md)

For artifact curation guidance (what to keep vs ignore):

- [`examples/README.md`](./examples/README.md)

---

## 1) What this repository is

This repo is a **Python `uv` workspace monorepo** for offline, cutoff-safe experimentation on PR routing.

Workspace members (`pyproject.toml`):

- `packages/ingestion`
- `packages/inference`
- `packages/experimentation`
- `packages/evaluation`
- `packages/cli`

Core idea:

- ingest GitHub metadata into a local SQLite history DB,
- build as-of PR inputs at a cutoff time,
- run routers (baselines + custom),
- evaluate against policy-driven truth labels,
- store deterministic artifacts for reproducibility.

---

## 2) One mental model for the whole system

```text
GitHub API
  -> ingestion (backfill/incremental/pull-requests --with-truth)
  -> data/github/<owner>/<repo>/history.sqlite
  -> inference (HistoryReader + input bundle + routers + artifacts)
  -> evaluation (streaming eval + truth + metrics + reports)
  -> data/github/<owner>/<repo>/eval/<run_id>/...
```

And the **recommended user-facing entry point** is now:

- `repo` CLI from `packages/cli`

It exposes ingestion, experiments, profile building, diagnostics, and direct `inference` / `evaluation` subcommands.

---

## 3) Project structure and where to look

### Top-level

- `data/` → local DB + run outputs
- `docs/` → architecture + plans + task docs
- `notebooks/` → marimo exploratory notebooks
- `experiments/` → reproducible experiment configs + export scripts + marimo experiment notebooks
- `scripts/` → validation scripts

### Package responsibilities

#### `packages/ingestion`

Builds/updates canonical `history.sqlite`.

Key files:

- CLI: `packages/ingestion/src/gh_history_ingestion/cli/app.py`
- Full backfill: `.../ingest/backfill.py`
- Incremental: `.../ingest/incremental.py`
- PR-window backfill: `.../ingest/pull_requests.py`
- Schema: `.../storage/schema.py`
- Upserts: `.../storage/upsert.py`
- Interval rebuild: `.../intervals/rebuild.py`
- Pinned artifact fetcher: `.../repo_artifacts/fetcher.py`

#### `packages/inference`

Reads local DB, reconstructs cutoff-safe snapshots, runs routers, writes routing artifacts.

Key files:

- CLI: `packages/inference/src/repo_routing/cli/app.py`
- As-of reader: `.../history/reader.py`
- Input bundle builder: `.../inputs/builder.py`
- Router contracts: `.../router/base.py`
- Router registry + plugin loading: `.../registry.py`
- Baselines: `.../router/baselines/*.py`
- Deterministic artifact writer: `.../artifacts/writer.py`
- Repo profile builder: `.../repo_profile/builder.py`
- Feature extractor v1: `.../predictor/feature_extractor_v1.py`

#### `packages/evaluation`

Streaming offline eval with truth extraction, metrics, reports, manifests.

Key files:

- CLI: `packages/evaluation/src/evaluation_harness/cli/app.py`
- Runner: `.../runner.py`
- Cutoff policy: `.../cutoff.py`
- Truth extraction: `.../truth.py`
- Truth policy system: `.../truth_policy.py`
- Metrics: `.../metrics/*.py`
- Reporting: `.../reporting/*.py`
- Paths: `.../paths.py`

#### `packages/experimentation`

Experiment orchestration, cohort/spec artifacts, quality gates, and notebook helper utilities.

Key files:

- Unified workflow logic: `packages/experimentation/src/experimentation/unified_experiment.py`
- Reusable notebook helpers: `packages/experimentation/src/experimentation/marimo_components.py`

#### `packages/cli`

Unified command surface around ingestion + experimentation + inference + evaluation.

Key files:

- CLI wiring: `packages/cli/src/repo_cli/cli.py`

---

## 4) Data model and artifact model

## 4.1 Canonical history DB

Default path:

- `data/github/<owner>/<repo>/history.sqlite`

Important table groups:

- identity: `repos`, `users`, `teams`, `labels`, `milestones`
- core objects: `issues`, `pull_requests`, `reviews`, `comments`, `pull_request_files`
- event log: `events` (append-only, normalized)
- as-of intervals: `*_intervals` tables (head/draft/review requests/content, etc.)
- ops quality: `watermarks`, `ingestion_gaps`, `qa_reports`

## 4.2 Eval run output

Default run dir:

- `data/github/<owner>/<repo>/eval/<run_id>/`

Typical files:

- `manifest.json`
- `report.json`
- `report.md`
- `per_pr.jsonl`
- `prs/<pr>/snapshot.json`
- `prs/<pr>/inputs.json`
- `prs/<pr>/routes/<router_id>.json`
- optional: `prs/<pr>/features/<router_id>.json`
- optional: `prs/<pr>/llm/<router_id>/<step>.json`
- optional: `prs/<pr>/repo_profile/profile.json`
- optional: `prs/<pr>/repo_profile/qa.json`
- from unified CLI: `experiment_manifest.json`, plus copies of `cohort.json` and `experiment.json`

---

## 5) Temporal safety model (critical)

This repo is built around **cutoff-safe computation**.

Rules:

- features and routing inputs must only use data `<= cutoff`
- as-of reconstruction uses interval tables, not mutable “latest state”
- no network calls in core routing/eval logic
- pinned artifacts only (e.g. CODEOWNERS at `base_sha`)

Implementation anchors:

- as-of snapshot reconstruction: `repo_routing.history.reader.HistoryReader`
- strict stale-cutoff guard: `evaluation_harness.runner.run_streaming_eval` (fails when cutoff exceeds DB event horizon in strict mode)

---

## 6) CLI surfaces (what to run)

## 6.1 Main front door

```bash
uv run --project packages/cli repo --help
```

Top-level commands currently include:

- `ingest`, `incremental`, `pull-requests`, `explore`
- `doctor`
- `cohort create`
- `experiment init|run|show|list|explain|diff`
- `profile build`
- `inference ...` (direct inference package CLI)
- `evaluation ...` (direct evaluation package CLI)

## 6.2 Recommended reproducible workflow

1. Create cohort (deterministic PR list + per-PR cutoffs)
2. Create experiment spec (routers + strictness + profile settings)
3. Run experiment with locked cohort/spec
4. Inspect/show/explain/diff

---

## 7) Your default experimentation loop (practical)

## Step 0: environment

```bash
uv venv
uv sync
```

## Step 1: ingest data

Full ingest:

```bash
uv run --project packages/cli repo ingest --repo <owner>/<repo>
uv run --project packages/cli repo incremental --repo <owner>/<repo>
```

PR-window ingest with truth signals:

```bash
uv run --project packages/cli repo pull-requests \
  --repo <owner>/<repo> \
  --from <iso> --end-at <iso> \
  --with-truth
```

## Step 2: preflight sanity

```bash
uv run --project packages/cli repo doctor --repo <owner>/<repo>
```

This checks (among others):

- DB exists and max event time
- stale cutoffs
- CODEOWNERS coverage for selected PRs
- ingestion gaps summary
- approval/merger readiness hints

## Step 3: cohort + spec

```bash
uv run --project packages/cli repo cohort create \
  --repo <owner>/<repo> \
  --from <iso> --end-at <iso> \
  --limit 200 --seed 4242 \
  --output cohort.json

uv run --project packages/cli repo experiment init \
  --repo <owner>/<repo> \
  --cohort cohort.json \
  --router mentions --router popularity --router codeowners \
  --output experiment.json
```

## Step 4: run

```bash
uv run --project packages/cli repo experiment run \
  --spec experiment.json \
  --data-dir data
```

## Step 5: inspect

```bash
uv run --project packages/cli repo experiment show --repo <owner>/<repo> --run-id <run_id>
uv run --project packages/cli repo experiment explain --repo <owner>/<repo> --run-id <run_id> --pr <n> --router <router_id>
uv run --project packages/cli repo experiment list --repo <owner>/<repo>
```

## Step 6: compare runs

```bash
uv run --project packages/cli repo experiment diff \
  --repo <owner>/<repo> \
  --run-a <run_a> --run-b <run_b>
```

By default, diff requires matching cohort hashes (override with `--force`).

---

## 8) Unified experiment artifacts: cohort + spec

### `cohort.json` (`kind=cohort`)

Includes:

- repo
- filters (time window, seed, limit)
- deterministic `pr_numbers`
- locked `pr_cutoffs` map
- content hash (`hash`)

### `experiment.json` (`kind=experiment_spec`)

Includes:

- repo
- optional cohort path/hash lock
- cutoff policy, strictness, top_k
- routers (`builtin` or `import_path`)
- repo profile settings (strict, artifact allowlist, critical artifacts)
- llm mode (`off|live|replay`)
- spec hash

Important behavior from `repo experiment run`:

- if spec locks cohort, inline cohort flags are rejected
- locked `pr_cutoffs` are used directly (no silent recompute)
- manifest captures prefetch network provenance if artifact fetching happens

---

## 9) Truth policies and evaluation semantics

Truth is now policy-driven.

Defaults (`EvalDefaults`):

- active policies: `first_response_v1`, `first_approval_v1`
- primary policy: `first_approval_v1`
- default truth window: 60 minutes
- default filters: exclude bots + PR author

Per-PR rows now carry:

- `truth_status`
- `truth_diagnostics`
- policy-keyed `truth.policies[...]`
- policy-keyed routing metrics (`routing_agreement_by_policy`)

Truth status values (`evaluation_harness.models.TruthStatus`):

- `observed`
- `no_post_cutoff_response`
- `unknown_due_to_ingestion_gap`
- `policy_unavailable`

This is important: the system can now separate “no response” vs “data-quality unknown”.

---

## 10) Repo profile and pinned artifacts

Repo profile is built per PR at cutoff (anchored by `base_sha`) and stored under run artifacts.

Builder:

- `repo_routing.repo_profile.builder.build_repo_profile`

Profile includes:

- identity/provenance
- pinned artifact manifest (with hashes)
- ownership graph
- area model
- policy signals
- vocabulary
- QA coverage report

Pinned artifact storage:

- `data/github/<owner>/<repo>/repo_artifacts/<base_sha>/...`
- manifest: `.../manifest.json`

Fetcher:

- `gh_history_ingestion.repo_artifacts.fetcher.fetch_pinned_repo_artifacts_sync`

Strict behavior:

- profile strict mode can fail run when CODEOWNERS or critical artifacts are missing.

---

## 11) Routers and extension points

## 11.1 Built-in routers

Implemented in registry (`repo_routing.registry._builtin_router`):

- `mentions`
- `popularity`
- `codeowners`
- `union`
- `hybrid_ranker`
- `llm_rerank`
- `stewards` (requires config)

## 11.2 Fastest way to experiment: import-path router

You can add a custom router without changing core registry by implementing a factory/class and passing `--router-import module:attr`.

Reference implementation:

- `packages/inference/src/repo_routing/examples/llm_router_example.py`

Contract:

- object with `.route(...) -> RouteResult`
- or `.predict(PRInputBundle, top_k)` via adapter

## 11.3 Writing a new built-in router

1. Add router class under `repo_routing/router/...`
2. Wire it in `repo_routing/registry.py`
3. Add validation entries where needed in CLI
4. Add tests (`packages/inference/tests` + runner integration tests)

---

## 12) Feature extraction stack (for model experiments)

Primary extractor:

- `AttentionRoutingFeatureExtractorV1` in `repo_routing/predictor/feature_extractor_v1.py`

Feature families (implemented modules):

- PR surface/meta/gates: `features/pr_surface.py`
- PR timeline/trajectory: `features/pr_timeline.py`
- Ownership/CODEOWNERS: `features/ownership.py`
- Candidate activity: `features/candidate_activity.py`
- Pair interaction features: `features/interaction.py`
- Repo priors: `features/repo_priors.py`
- PR similarity: `features/similarity.py`
- Automation signals: `features/automation.py`

Governance metadata:

- feature registry: `features/feature_registry.py`
- task policy registry: `features/task_policy.py`

When adding features, also update registry/task policy so quality checks stay useful.

Validation utilities:

- `scripts/check_feature_quality.py`
- `scripts/validate_feature_stack.sh`

---

## 13) Determinism and guardrails you should preserve

Determinism mechanisms:

- stable sorted JSON writers in artifacts/reporting
- deterministic router IDs (`router_id_for_spec`)
- deterministic cohort/spec hashing

Guardrails:

- strict stale-cutoff fail in streaming eval
- as-of interval reconstruction for snapshots
- bot/author filtering in truth/queue logic
- pinned CODEOWNERS handling

Experiment quality gates (in `repo experiment run`, profile=`audit`):

- truth window consistency
- truth policy schema presence
- unknown ingestion-gap rate threshold
- ownership availability threshold
- router unavailable-rate threshold
- basic deterministic reproducibility check

In audit mode, failing gates can cause non-zero exit.

---

## 14) What to modify for common experiment types

## A) “I want to try a new ranking idea quickly”

Best path:

- create import-path router using predictor pipeline
- reuse `PRInputBundle`
- run via `repo experiment init --router-import ...`

Files to copy inspiration from:

- `repo_routing/examples/llm_router_example.py`
- `repo_routing/predictor/pipeline.py`
- `repo_routing/router/base.py`

## B) “I want to add new engineered features”

1. implement in one or more `predictor/features/*.py`
2. compose in `feature_extractor_v1.py`
3. classify in `feature_registry.py`
4. adjust `task_policy.py` if needed
5. add/update tests

## C) “I want new truth semantics”

- add/adjust policy in `evaluation_harness/truth_policy.py`
- implement extraction branch in `evaluation_harness/truth.py`
- ensure outputs follow `TruthDiagnostics`/policy-keyed contract
- add tests under `packages/evaluation/tests`

## D) “I want richer repo profile understanding”

- extend parsers in `repo_routing/repo_profile/parsers/`
- evolve builder logic in `repo_profile/builder.py`
- keep strict deterministic outputs + provenance

---

## 15) Troubleshooting quick map

- **`strict_streaming_eval violation`**
  - DB horizon too old for cutoffs. Refresh ingestion or use non-strict mode intentionally.

- **CODEOWNERS missing / profile strict failure**
  - prefetch artifacts or disable strict repo profile for exploratory runs.
  - check `repo profile build --allow-fetch-missing-artifacts`.

- **Unknown router or config errors**
  - check names in `repo_routing.registry._builtin_router`
  - `stewards` requires config path.

- **No PRs selected**
  - verify cohort window/filter and DB content.

- **As-of reader errors (`missing *_intervals`)**
  - ingestion intervals likely missing; re-run ingestion/rebuild path.

---

## 16) Notebook and UI helpers

Notebook utilities exist for interactive workflows:

- `notebooks/ghostty_marimo_pipeline.py` (ingest/export/eval loop)
- `notebooks/experiment_audit_...py` (run auditing)
- reusable marimo components in `experimentation/marimo_components.py` (`packages/experimentation/src/experimentation/marimo_components.py`)

These are helpful for exploration, but CLI artifacts remain the canonical source of reproducible experiment state.

---

## 17) Suggested “first 3” experiments to run now

1. **Baseline stability check**
   - routers: mentions, popularity, codeowners
   - same cohort, rerun twice, verify comparable outputs

2. **Deterministic hybrid vs popularity**
   - routers: popularity, union, hybrid_ranker
   - compare MRR on observed-and-nonempty slice

3. **Replay LLM rerank over deterministic stack**
   - routers: hybrid_ranker, llm_rerank (mode=replay)
   - inspect llm provenance + per-step artifacts

---

## 18) Final practical advice

If you’re deciding where to spend effort first:

- use `repo experiment` workflow (cohort/spec locking) for any result you might keep,
- prototype router ideas as import-path plugins before making core-package changes,
- keep cutoff safety and deterministic outputs as non-negotiable,
- and use `report.json + per_pr.jsonl + experiment_manifest.json` as your source of truth for analysis.

If you want, I can also generate a **second companion doc** that is just a “cookbook” (copy-paste commands + templates for new router/feature/truth-policy experiments).