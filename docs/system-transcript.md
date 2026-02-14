# Ghostty-Analysis System Transcript (Router-Only)

## 1) Executive Summary (1 page max)

This repository is an offline, leakage-safe experimentation stack for **reviewer/owner attention routing** on GitHub pull requests. It ingests GitHub history into a local SQLite database, runs one or more **routers** against PRs at explicit **as-of cutoffs**, evaluates router outputs against configurable **truth policies**, and produces deterministic artifacts (JSON/JSONL/Markdown) that can be compared across runs.

The monorepo is a `uv` workspace with six packages:

- `ingestion`: builds `history.sqlite` (the canonical, offline data substrate).
- `inference` (`repo_routing`): defines router contracts, router specs/IDs, input builders, and deterministic per-PR artifacts.
- `evaluation` (`evaluation_harness`): orchestrates cutoff-safe routing + truth extraction + metrics + reporting.
- `experimentation`: wraps evaluation into reproducible “cohort/spec/run” workflows, adds quality gates/promotion checks, and provides run comparison tooling.
- `core` (`sdlc_core`): shared primitives for stable hashing and run IDs.
- `cli` (`repo_cli`): unified `repo ...` command that mounts the other CLIs.

The system’s central invariant is **cutoff safety**:

- Every routed decision is computed for `(repo, pr_number, cutoff)`.
- All feature reads must be bounded by the cutoff (no post-cutoff leakage).
- By default, evaluation enforces a “streaming” safety check: cutoffs cannot exceed the database’s known event horizon.

The system is **router-only**:

- Outputs, metrics, and APIs are expressed in terms of routers and `router_id`.
- Legacy “baseline” terminology is intentionally not part of the current contract (builtin routers may still exist; they are still routers).

On disk, a run is a directory:

`data/github/<owner>/<repo>/eval/<run_id>/`

containing:

- `manifest.json`: run configuration, router specs, truth policy metadata, PR list + cutoffs.
- `per_pr.jsonl`: one row per PR with truth + gates + router outputs + per-PR metrics.
- `report.json` and `report.md`: aggregated metrics and summaries.
- `prs/<pr>/...`: deterministic per-PR artifacts like `snapshot.json`, `inputs.json`, and `routes/<router_id>.json`.

The primary user experience is the unified CLI:

`uv run --project packages/cli repo ...`

For most work, you will:

1. Ingest: `repo ingestion ingest` (or `incremental`).
2. Define a cohort: `repo cohort create`.
3. Define a spec: `repo experiment init`.
4. Run: `repo experiment run`.
5. Inspect/compare: `repo experiment show|explain|diff|compare`.

Extensibility is designed around stable seams:

- Add a new router behind the `Router.route(...) -> RouteResult` contract.
- Add/adjust truth policies via `TruthPolicySpec` + allowlisted plugins.
- Add metrics by consuming `per_pr.jsonl` rows and/or the in-memory aggregation stage.
- Treat artifact schemas and directory layouts as contracts; bump versions when incompatible.

If you change contracts (schemas, paths, terminology), you must update:

- CLI flags + help text, output writers, and readers (`explain`, `show`, `diff`).
- Schema versions in artifacts (`kind`/`version`).
- Tests that validate import boundaries and end-to-end runs.
- Documentation that describes the current contracts (docs can drift; see guardrails).

---

## 2) Mental Model of the System (components + responsibilities)

Think of the system as a deterministic pipeline whose “unit of evaluation” is a PR at a cutoff:

`(repo, pr_number, cutoff) -> RouteResult -> metrics/reporting`.

### High-level flow

```mermaid
flowchart TD
  subgraph DataSubstrate[Offline data substrate]
    DB[history.sqlite]
    Pinned[Pinned artifacts\n(e.g., CODEOWNERS @ base_sha)]
  end

  subgraph Inference[Inference / Routing]
    Snap[PR snapshot @ cutoff]
    Inputs[PR inputs bundle @ cutoff]
    Router[Router(s)]
    Route[RouteResult]
    Artifacts[Deterministic PR artifacts\n(snapshot.json, inputs.json, routes/<router_id>.json)]
  end

  subgraph Evaluation[Evaluation harness]
    Cutoff[Cutoff selection + streaming safety]
    Truth[Truth extraction\n(policy-driven)]
    Metrics[Metrics aggregation\n(hit@k, MRR, gates, queue)]
    Outputs[Run outputs\nmanifest.json, per_pr.jsonl, report.json/md]
  end

  subgraph Experimentation[Experiment workflows]
    Cohort[Cohort: PR list + per-PR cutoffs + hash]
    Spec[Spec: routers + settings + hash]
    Gates[Quality gates + promotion checks]
    Compare[Diff/compare across runs]
  end

  DB --> Snap
  DB --> Inputs
  Pinned --> Inputs
  Cutoff --> Snap
  Cutoff --> Inputs
  Inputs --> Router
  Router --> Route
  Route --> Metrics
  Truth --> Metrics
  Snap --> Artifacts
  Inputs --> Artifacts
  Route --> Artifacts
  Metrics --> Outputs
  Cohort --> Cutoff
  Spec --> Router
  Outputs --> Gates
  Outputs --> Compare
```

### Component responsibilities

- `ingestion` (GitHub -> SQLite):
  - Creates and incrementally updates `history.sqlite` under `data/github/<owner>/<repo>/`.
  - Stores canonical entities/events and derived interval tables.
  - Records ingestion gaps and QA summaries inside the DB.

- `inference` / `repo_routing` (routing contract + deterministic artifacts):
  - Defines the routing output contract (`RouteResult`).
  - Builds cutoff-safe PR snapshots and optional input bundles.
  - Loads routers from specs and executes them without network access.
  - Writes deterministic JSON artifacts into the eval run directory.

- `evaluation` / `evaluation_harness` (orchestrate + score):
  - Selects PRs and computes cutoffs.
  - Enforces streaming/leakage guardrails.
  - Computes “truth” targets for evaluation (policy-driven; can be unavailable).
  - Computes per-PR and aggregate metrics.
  - Writes `manifest.json`, `per_pr.jsonl`, and `report.json`/`report.md`.

- `experimentation` (reproducible runs + gates):
  - Freezes “what we ran” into hashed `cohort.json` and `experiment.json`.
  - Runs evaluation harness with those locked inputs.
  - Post-processes reports with quality gates and promotion checks.
  - Provides diff/compare/summarize commands.

- `core` / `sdlc_core` (shared determinism primitives):
  - Stable JSON hashing.
  - Run ID computation.
  - Minimal artifact/run metadata types (used opportunistically).

- `cli` / `repo_cli` (unified UX):
  - The `repo` command mounts ingestion + experimentation always.
  - Inference/evaluation subcommands are optional; if import fails, `repo` enters “degraded mode” for that group.

---

## 3) Repository & Package Map (what lives where, why boundaries exist)

### Workspace layout

```
.
├── data/                 # local artifacts, sqlite, eval outputs (not committed)
├── docs/                 # architecture + plans + onboarding docs
├── notebooks/            # marimo notebooks and demos
├── experiments/          # reusable experiment configs/extract scripts
├── packages/
│   ├── core/
│   ├── ingestion/
│   ├── inference/
│   ├── experimentation/
│   ├── evaluation/
│   └── cli/
├── scripts/              # validation scripts
├── pyproject.toml        # uv workspace members
└── uv.lock
```

### Why these package boundaries exist

- `ingestion` is intentionally separated because it is the only place that is allowed to talk to GitHub (network) and mutate the historical substrate.
- `inference` is intentionally “pure offline”: it must route from `history.sqlite` + pinned artifacts only.
- `evaluation` is the orchestrator and scorekeeper; it consumes router outputs, not raw GitHub APIs.
- `experimentation` is the reproducibility layer: it decides *what* set of PRs and settings constitute a run, hashes them, and defines the promotion workflow.
- `core` exists because stable hashing/run IDs and minimal typed refs are cross-cutting needs; it prevents subtle divergence in hashing/ID logic.
- `cli` is a thin composition layer so operators have one entrypoint (`repo`) while still allowing package-level CLIs (`ingestion`, `inference`, `evaluation`) for debugging.

### Stable import surfaces (where downstream code should import from)

- `sdlc_core.*` for hashing and run-id primitives.
- `repo_routing.api` for router spec parsing/loading helpers.
- `evaluation_harness.api` for programmatic run orchestration.

Avoid importing from deep internal modules unless you are actively evolving them; stable public surfaces reduce drift.

---

## 4) Canonical Data Contracts

This section is the “contract layer”: if you change these, you are changing the system.

### 4.1 Route artifact schema (router_id, versions, paths)

There are two key artifact types written per PR:

1) PR snapshot artifact (`snapshot.json`)

- Path:
  - `data/github/<owner>/<repo>/eval/<run_id>/prs/<pr_number>/snapshot.json`
- Model: `PRSnapshotArtifact` (`kind="pr_snapshot"`, `version="v0"`).
- Purpose: capture exactly what the router was allowed to see at the cutoff.

Canonical fields (conceptual):

- Identity: `repo`, `pr_number`, `as_of`.
- PR content: `author`, `title`, `body`.
- Git anchors: `base_sha`, `head_sha`.
- Review context: `changed_files[]`, `review_requests[]`.

2) Route result artifact (`routes/<router_id>.json`)

- Path:
  - `data/github/<owner>/<repo>/eval/<run_id>/prs/<pr_number>/routes/<router_id>.json`
- Model: `RouteArtifact` (`kind="route_result"`, `version="v1"`).

Canonical fields:

- `router_id: str` (the current router-only identity; used everywhere).
- `result: RouteResult` (the canonical router output).
- `meta: dict` (small provenance/feature metadata; keep large payloads elsewhere).

`RouteResult` is the stable routing contract:

```text
RouteResult:
  repo: str
  pr_number: int
  as_of: datetime
  top_k: int
  candidates: list[ { target: {type: user|team, name: str}, score: float, evidence: list[{kind: str, data: dict}] } ]
  risk: str
  confidence: str
  notes: list[str]
```

Invariants:

- `as_of` in `RouteResult` must equal the PR cutoff used for that row.
- `candidates` is ranked (highest score first by convention).
- Evidence must be compact and deterministic; do not embed megabyte payloads.

Optional per-PR, per-router artifacts:

- `features/<router_id>.json` (only if the router exposes pipeline features).
- `llm/<router_id>/<step>.json` (only if an LLM router records steps; mode-dependent).

Drift risk to watch:

- Multiple modules define run/PR paths (`evaluation_harness.paths` and `repo_routing.artifacts.paths`). They currently agree; if you touch them, update both or centralize.

### 4.2 Eval artifacts (`per_pr.jsonl`, `report.json`, `manifest.json`)

All evaluation outputs live under the eval run directory:

`data/github/<owner>/<repo>/eval/<run_id>/`

#### `per_pr.jsonl` (one JSON object per line)

Path:

- `.../per_pr.jsonl`

Purpose:

- The canonical “row store” for analysis and debugging. It contains per-PR truth, gates, router outputs, and per-PR metrics.

Current row shape (conceptual; fields are stable enough to treat as contract):

```text
{
  repo: str,
  run_id: str,
  pr_number: int,
  cutoff: str (ISO8601),

  truth_behavior: list[str],                 # primary truth targets (legacy name; still present)
  truth_status: str,                         # observed|no_post_cutoff_response|unknown_due_to_ingestion_gap|policy_unavailable
  truth_diagnostics: {...},                  # primary truth diagnostics
  truth: {
    version: "v1",
    primary_policy: str,
    policies: {
      <policy_id>: {
        targets: list[str],
        status: str,
        diagnostics: {...},
        policy_hash: str,
        policy_source: str,
        policy_source_ref: str|None,
      },
      ...
    }
  },

  gates: {...},

  routers: {
    <router_id>: {
      route_result: {...RouteResult...},
      feature_meta: {...},
      routing_agreement: {...},
      routing_agreement_by_policy: { <policy_id>: {...}, ... },
      queue: {...}
    },
    ...
  },

  repo_profile: {...} | omitted
}
```

Invariants and interpretation:

- `truth_status` governs metric denominators; do not blindly average across rows without slicing.
- `routers.<router_id>.route_result.candidates` can be empty; agreement metrics treat this as “no recommendation.”
- `truth_behavior` is still present for back-compat, but the authoritative truth contract is `truth.version="v1"`.

#### `report.json` (aggregate summaries)

Path:

- `.../report.json`

Model: `EvalReport` (`kind="eval_report"`, `version="v0"`).

Top-level fields:

- `repo`, `run_id`, `generated_at`.
- DB horizon metadata: `db_max_event_occurred_at`, `db_max_watermark_updated_at`.
- `package_versions`: captured versions for traceability.
- `routers: list[str]` (router IDs evaluated).
- `routing_agreement`: per-router aggregate routing metrics (and policy slices in `extra`).
- `gates`: aggregate gate correlation summary (optional).
- `queue`: per-router queue summaries.
- `notes`: human-readable caveats.
- `extra`: an extension point; experimentation uses this to persist quality gate results.

Interpretation:

- Treat `report.json` as the stable “dashboard payload.”
- Treat `per_pr.jsonl` as the stable “debug and analysis payload.”

#### `manifest.json` (run manifest)

Path:

- `.../manifest.json`

Model: `EvalManifest` (`kind="eval_manifest"`, `version="v0"`).

Key fields:

- `repo`, `run_id`, `generated_at`.
- DB horizon metadata + package versions.
- `routers`: router specs as JSON objects (not just IDs).
- `router_feature_meta`: per-router provenance/feature metadata captured during the run.
- `cutoff_source`: where cutoffs came from (policy vs cohort lock).
- `pr_cutoffs`: per-PR cutoff timestamps (stringified).
- `truth`: truth policy metadata (active policies, hashes, source refs).
- `config`: full serialized `EvalRunConfig`.
- `pr_numbers`: the PRs evaluated.

Invariant:

- `manifest.json` must be sufficient to explain “what was run” without reading code.

#### Compare outputs

Comparisons are written under:

- `data/github/<owner>/<repo>/eval/_compare/<run_a>__vs__<run_b>/compare_summary.json`

This is a derived artifact; it is not an input contract.

### 4.3 Run IDs / hashing / shared core primitives

Three “identity” mechanisms appear throughout the system:

1) `run_id` (evaluation run directory identity)

- Computed as:
  - `YYYYmmddTHHMMSSZ-<sha256_prefix>`
- Hash input is the **run config payload** with `run_id` excluded.
- Source of truth: `sdlc_core.ids.compute_run_id` (shared), wrapped by `evaluation_harness.run_id`.

Operational consequence:

- The timestamp makes run IDs human-sortable and unique across time, but not reproducible unless you inject `now`.
- The hash prefix makes collisions unlikely but not impossible; do not rely on `run_id` as a cryptographic commitment.

2) Cohort hash (`cohort.json`)

- `experimentation` produces a deterministic cohort payload including per-PR cutoffs and stores `hash = stable_hash_json(payload_without_hash)`.
- This hash is used as a lock when comparing/promoting runs.

3) Spec hash (`experiment.json`)

- `experimentation` similarly hashes the spec payload, including router specs and run settings.
- Spec locks are used to prevent “accidental apples-to-oranges” comparisons.

Hashing invariant:

- All stable hashes are based on canonical JSON with sorted keys and ASCII output. If you add fields, you change hashes.

---

## 5) End-to-End Workflows

This section describes the canonical “happy path” and where each CLI fits.

### 5.1 Ingest -> inference/routing -> experimentation -> evaluation -> reporting

Although the packages are distinct, the operational pipeline is linear:

1) Ingestion produces `history.sqlite`.

- Input: `--repo owner/name` and optional time windows.
- Output: `data/github/<owner>/<repo>/history.sqlite`.
- Key invariants:
  - Idempotent upserts and deterministic event keys.
  - Derived interval tables are rebuilt after ingest stages.

2) Experimentation selects PRs and cutoffs.

- Cohort creation picks PR numbers (either explicit or sampled from a window) and computes a per-PR cutoff using the configured cutoff policy.
- Output: `cohort.json` with `pr_numbers`, `pr_cutoffs`, and a stable `hash`.

3) Spec creation selects routers and run settings.

- Router specs can refer to builtin routers by name or import routers by Python import path.
- Output: `experiment.json` with router specs and a stable `hash`.

4) Evaluation harness runs routers at cutoffs and writes run outputs.

- For each PR:
  - Writes `snapshot.json` and `inputs.json`.
  - Computes truth for one or more truth policies.
  - Executes each router’s `route(...)`.
  - Writes `routes/<router_id>.json`.
  - Appends one row to `per_pr.jsonl`.
- End of run:
  - Writes `manifest.json`, `report.json`, and `report.md`.

5) Experimentation post-processes outputs (when using unified workflow).

- Adds quality gate blocks into `report.json.extra`.
- Generates summary artifacts for promotion/compare.
- Enforces “audit” mode by exiting non-zero when gates fail.

### 5.2 Primary CLI entrypoints and when to use each

The recommended UX is the unified CLI:

- `uv run --project packages/cli repo ...`

Use package CLIs directly when:

- You need to debug a single layer in isolation.
- The unified CLI is in “degraded mode” for an optional group.

Canonical entrypoints:

- Unified CLI:
  - `uv run --project packages/cli repo --help`
- Ingestion-only CLI:
  - `uv run --project packages/ingestion ingestion --help`
- Inference-only CLI:
  - `uv run --project packages/inference inference --help`
- Evaluation-only CLI:
  - `uv run --project packages/evaluation evaluation --help`

Practical guidance:

- Operators typically run `repo ingestion ...` once and then iterate on `repo cohort/experiment/evaluation ...` many times.
- Engineers implementing routers typically iterate with `repo evaluation run --router ...` on a small PR subset, then move into `repo experiment ...` once stable.

---

## 6) User Journeys (at least 3)

### Journey A: First-time local run

Goal: ingest one repository, run a small evaluation, and see a report.

1) Create a venv and sync dependencies:

```bash
uv venv
uv sync
```

2) Ingest history:

```bash
uv run --project packages/cli repo ingestion ingest --repo owner/name
```

Expected output:

- `data/github/owner/name/history.sqlite` exists and grows.

3) Create a cohort (pick a small window and limit):

```bash
uv run --project packages/cli repo cohort create \
  --repo owner/name \
  --from 2025-01-01T00:00:00Z \
  --end-at 2025-02-01T00:00:00Z \
  --limit 25 \
  --output cohort.json
```

4) Create an experiment spec (choose routers; defaults exist):

```bash
uv run --project packages/cli repo experiment init \
  --repo owner/name \
  --cohort cohort.json \
  --output experiment.json
```

5) Run:

```bash
uv run --project packages/cli repo experiment run --spec experiment.json
```

6) Inspect:

```bash
uv run --project packages/cli repo experiment show --repo owner/name --run-id <run_id>
uv run --project packages/cli repo experiment explain --repo owner/name --run-id <run_id> --pr <pr_number>
```

What you should know during the first run:

- A run can fail early if the DB horizon is behind your requested cutoffs (strict streaming eval).
- A run can fail if repo-profile is enabled + strict and pinned artifacts (CODEOWNERS / critical files) are missing.

### Journey B: Adding or changing a router

Goal: implement a new router and evaluate it without breaking contracts.

1) Decide the integration mode:

- Builtin router (in-tree): add under `packages/inference/src/repo_routing/router/` and register it.
- Import-path router (out-of-tree): implement in another module and reference it via `--router-import` / router spec `type=import_path`.

2) Implement the router contract:

- Provide `route(repo, pr_number, as_of, data_dir="data", top_k=5, input_bundle=None) -> RouteResult`.
- Ensure all reads are cutoff-safe:
  - SQL queries must explicitly bound by `<= as_of`.
  - Pinned artifacts must be keyed by stable anchors like `base_sha`.
  - No network calls.

3) Decide `router_id` stability:

- Builtin: `router_id` is the router name (lowercased).
- Import-path: `router_id` is derived from import path + config hash.

Router ID stability matters because:

- Artifact path is `routes/<router_id>.json`.
- `per_pr.jsonl` uses `routers.<router_id>`.
- Reports and diff tools key off router IDs.

4) Evaluate on a small set:

```bash
uv run --project packages/cli repo evaluation run \
  --repo owner/name \
  --router <your_router_name_or_id> \
  --pr 123 --pr 456 \
  --run-id dev-router-test
```

5) Verify artifacts:

- `.../eval/dev-router-test/prs/123/routes/<router_id>.json` exists.
- `.../eval/dev-router-test/per_pr.jsonl` contains a `routers.<router_id>` object.

6) If the router needs configuration:

- Provide a deterministic config file and pass it through router spec config mechanisms.
- Expect config changes to change the derived `router_id` (import-path routers) and therefore change output paths.

### Journey C: Running and interpreting eval results

Goal: run two router variants and compare them, safely.

1) Run two experiments with the same cohort:

```bash
uv run --project packages/cli repo experiment run --spec experiment_a.json
uv run --project packages/cli repo experiment run --spec experiment_b.json
```

2) Compare:

```bash
uv run --project packages/cli repo experiment diff \
  --repo owner/name \
  --run-a <run_id_a> \
  --run-b <run_id_b>
```

Interpretation rules:

- If cohort hashes differ, the diff command will refuse (unless forced) because metrics are not comparable.
- Always inspect denominators/slices:
  - truth unavailable (policy unavailable / ingestion gap) can dominate naive averages.
- When a router’s candidate list is empty:
  - hit@k will be 0, and this may or may not be actionable (e.g., router intended to abstain).

Debugging a surprising result:

- Use `repo experiment explain` (or `repo evaluation explain`) for a specific PR and router ID.
- Cross-check `prs/<pr>/snapshot.json` and `prs/<pr>/inputs.json` to ensure the router is seeing what you think.
- Confirm the cutoff is what you intended (`manifest.json.pr_cutoffs`).

---

## 7) Operational Rules & Guardrails

This section states the rules that make results meaningful.

### 7.1 Cutoff behavior (streaming safety)

Cutoff is a first-class input to routing and truth extraction.

- Cutoff policies include `created_at`, `ready_for_review`, and `created_at+<delta>`.
- Evaluation preflight computes a database “event horizon” (maximum event occurred-at timestamp).
- If `strict_streaming_eval` is enabled (default in experimentation), evaluation fails if any cutoff exceeds the event horizon.

Why it matters:

- It prevents “future knowledge” in routing features/truth extraction.

Failure mode:

- A fresh run fails immediately with a message indicating the cutoff exceeded `db_max_event_occurred_at`.

Fix:

- Run ingestion incremental/backfill to advance the DB horizon, or move your cohort window/cutoff policy earlier.

### 7.2 Truth policy behavior

Truth is policy-driven and can be unavailable.

- A “truth policy” defines how to select a target user/team from post-cutoff events.
- Policies are hashed and recorded in `per_pr.jsonl` and `manifest.json`.
- Truth extraction produces:
  - `status`: observed / no_post_cutoff_response / unknown_due_to_ingestion_gap / policy_unavailable
  - diagnostics for debugging “why truth was/was not observed”.

Operational consequence:

- Metrics must slice by truth status (especially ingestion gaps).
- A policy can be configured but not implemented at engine level; the status becomes `policy_unavailable`.

### 7.3 Router-only terminology contract

Current contracts are router-only:

- Artifacts are keyed by `router_id`.
- Reports list `routers` only.
- CLI flags use `--router` and router specs.

Historical note:

- Some files and docs may still contain “baseline” in filenames or narrative. Treat these as historical language; the operational contract is still router-only.

### 7.4 Compatibility assumptions and migration caveats

Assumptions that are effectively part of the system contract:

- Repo identity is always `owner/name` and becomes part of the directory path.
- The run directory layout under `data/github/.../eval/<run_id>/` is stable.
- Deterministic JSON writing (sorted keys, ASCII, stable formatting) is relied upon for diffing and hashing.

Migration caveats when you change contracts:

- If you bump an artifact schema version, you must keep readers (`explain`, `diff`, summary generators) compatible or provide explicit migration tooling.
- If you change `router_id` derivation, you are changing output paths and report keys. Expect downstream comparisons to break.
- If you change truth policy defaults, you change denominators and the meaning of metrics.

Docs/implementation drift hotspots:

- `docs/attention-routing/architecture.md` is close to reality but contains legacy truth terminology in places; treat code as authoritative for truth policy behavior.

---

## 8) Architecture Decision Log (Current State)

This is a “current state ADR” capturing the refactors that define today’s system.

### 8.1 Introduced `packages/core` shared primitives

Decision:

- Centralize stable hashing and run ID generation in `sdlc_core`.

Why it matters:

- Hashes and run IDs are cross-cutting reproducibility primitives.
- Centralization reduces subtle divergence (e.g., JSON canonicalization differences).

Risk/tradeoff:

- If downstream packages bypass core primitives, drift returns. Enforce usage via tests and code review.

### 8.2 Removed transitional evaluation “harness namespace”

Decision:

- Evaluation package surface is now `evaluation_harness` directly.

Why it matters:

- Reduces ambiguity about “the harness” vs other orchestrators.
- Makes imports stable (`evaluation_harness.api`, `evaluation_harness.cli`).

Risk/tradeoff:

- Any external code using transitional imports must update; keep small shims only if necessary.

### 8.3 Router-only terminology and contracts

Decision:

- The system’s conceptual and operational unit is the router.
- Artifacts, CLIs, and reports use `router_id` and router specs.

Why it matters:

- Removes dual-language confusion (routers vs “baselines”).
- Makes comparison and promotion logic uniform.

Risk/tradeoff:

- Some in-tree routers are still under directories historically named `baselines/`. That is naming debt, not a contract.

### 8.4 Inference CLI uses `--router` and route artifacts moved to `router_id` with schema bump

Decision:

- Route artifacts are written as `routes/<router_id>.json` using `RouteArtifact(version="v1")`.

Why it matters:

- `router_id` becomes the stable identity for artifacts and reporting.

Risk/tradeoff:

- Any consumer expecting older artifact names/paths must migrate.
- If router ID derivation changes, old artifacts become “orphaned” relative to new IDs.

### 8.5 Evaluation reporting/manifest/per-PR outputs updated for router-only

Decision:

- `per_pr.jsonl` and `report.json` are keyed by routers and carry truth policy metadata.

Why it matters:

- Enables multi-policy truth evaluation and policy-aware metric slicing.

Risk/tradeoff:

- `truth_schema.py` and docs can drift from what `per_pr.jsonl` actually emits; treat `runner_per_pr` as the source of truth.

---

## 9) How to Extend the System Safely

This section is the “change playbook.”

### 9.1 Recommended design seams

Router seam (most common):

- Implement a new router that returns `RouteResult`.
- Prefer using `PRInputBundle` (built once per PR) rather than ad-hoc SQL scattered across routers.

Truth seam:

- Add a new truth policy spec and implementation.
- Ensure it declares “policy_unavailable” if not implemented to avoid silent wrong truth.

Metric seam:

- Add new metrics by consuming per-PR rows and aggregating.
- Keep the metric output stable and record versioning in `report.json.extra`.

Artifact seam:

- If you need additional large payloads, add new per-PR artifacts under `prs/<pr>/...` rather than bloating `per_pr.jsonl`.
- Version any new artifact with `kind`/`version`.

### 9.2 Testing strategy and required validation commands

Suggested minimum validation when changing routing/eval behavior:

1) Package tests (fast):

```bash
uv run --project packages/inference pytest
uv run --project packages/evaluation pytest
uv run --project packages/experimentation pytest
uv run --project packages/cli pytest
```

2) Feature stack validation script (integration-focused):

```bash
./scripts/validate_feature_stack.sh
```

3) Smoke run on a small PR set (local data required):

```bash
uv run --project packages/cli repo evaluation run --repo owner/name --pr 123 --router mentions --run-id smoke
```

Contract tests you should not break:

- CLI smoke tests in `packages/cli/tests/`.
- Evaluation end-to-end tests in `packages/evaluation/tests/`.
- Import boundary tests (ensuring packages only depend on allowed layers).

### 9.3 Rollout checklist for non-backward-compatible changes

If you break compatibility (schemas, paths, IDs, terminology), do all of the following:

1) Explicitly bump schema versions:

- Update `kind`/`version` fields in Pydantic models.

2) Provide a reader strategy:

- Either support reading old versions or provide a migration script.

3) Update all “consumers”:

- `evaluation explain`, `experiment diff/compare/summarize`, any notebook utilities.

4) Update docs that operators rely on:

- `docs/attention-routing/architecture.md` and this transcript.

5) Run the full validation stack:

- Unit tests + integration validation.

6) Capture the decision:

- Add/extend an ADR entry (even if informal) describing why the break was necessary.

---

## 10) Troubleshooting Playbook (symptoms -> likely causes -> fixes)

### Symptom: `repo evaluation ...` or `repo inference ...` says “degraded mode”

Likely causes:

- Optional package import failed (dependency mismatch, missing optional dependency).

Fixes:

- Run `uv sync` to ensure workspace deps are installed.
- Run the package CLI directly to get a fuller traceback:
  - `uv run --project packages/evaluation evaluation --help`
  - `uv run --project packages/inference inference --help`

### Symptom: Evaluation run fails with a streaming/leakage error about cutoffs

Likely causes:

- `strict_streaming_eval=True` and `cutoff > db_max_event_occurred_at` for at least one PR.

Fixes:

- Run `repo ingestion incremental --repo owner/name` (or backfill) to update the DB.
- Shift cohort window earlier or change cutoff policy.

### Symptom: Truth status is frequently `unknown_due_to_ingestion_gap`

Likely causes:

- Ingestion recorded pagination gaps or missing event ranges.
- Truth policies require events that were not ingested (`--with-truth` not used for PR-only ingest).

Fixes:

- Re-ingest the relevant windows with truth-related resources enabled (PR reviews/comments/events).
- Inspect ingestion QA/gaps tables (via `repo ingestion explore`).

### Symptom: `repo_profile` fails or is skipped for many PRs

Likely causes:

- Missing `base_sha` in snapshots.
- Missing pinned artifacts (CODEOWNERS / critical files) for that `base_sha`.
- Strict mode enabled.

Fixes:

- Ensure pinned artifacts are fetched/available for the base SHAs being evaluated.
- Disable strict mode for repo-profile temporarily (for exploratory work), but record that in notes.

### Symptom: Router produces empty candidates for most PRs

Likely causes:

- Router depends on inputs not present (e.g., expects repo profile but it is missing).
- SQL queries are incorrectly bounded (too strict cutoff filtering).
- Router is configured for abstention mode.

Fixes:

- Inspect `prs/<pr>/inputs.json` and `prs/<pr>/repo_profile/profile.json` (if present).
- Add deterministic debug evidence (small) to `RouteCandidate.evidence`.
- Validate queries against a known PR by stepping through with a small subset.

### Symptom: `experiment diff` refuses due to cohort mismatch

Likely causes:

- Runs were produced from different PR sets or cutoffs.

Fixes:

- Re-run using the same `cohort.json`.
- Use `--force` only when you are intentionally doing apples-to-oranges exploration.

---

## 11) Glossary (plain-English definitions)

- Router: A deterministic function that recommends targets (users/teams) for a PR at an as-of cutoff.
- `router_id`: The stable identity used to name router outputs and keys in reports/artifacts.
- Cutoff: A timestamp defining the “as-of” point; the system must not use any data after this time.
- Truth policy: A rule for determining the “correct” target(s) from post-cutoff events for evaluation.
- `history.sqlite`: The local, canonical, offline database produced by ingestion.
- Pinned artifacts: Files fetched/stored under `data/` keyed by stable anchors (e.g., CODEOWNERS at a commit SHA) to avoid using a mutable checkout.
- Cohort: A locked list of PRs plus locked per-PR cutoffs, hashed for reproducibility.
- Experiment spec: A locked set of routers and run settings, hashed for reproducibility.
- `per_pr.jsonl`: The per-PR row log containing truth + router outputs + per-PR metrics.
- `report.json`: Aggregated metrics and summaries for a run.
- `manifest.json`: The run manifest capturing configuration and provenance.
- Streaming eval: Running PRs in cutoff order and enforcing that cutoffs do not exceed the DB’s event horizon.

---

## 12) Appendix

### 12.1 Command cheat sheet

Unified CLI (recommended):

```bash
uv run --project packages/cli repo --help
```

Ingest:

```bash
uv run --project packages/cli repo ingestion ingest --repo owner/name
uv run --project packages/cli repo ingestion incremental --repo owner/name
uv run --project packages/cli repo ingestion explore
```

Cohort/spec/run:

```bash
uv run --project packages/cli repo cohort create --repo owner/name --limit 50 --output cohort.json
uv run --project packages/cli repo experiment init --repo owner/name --cohort cohort.json --output experiment.json
uv run --project packages/cli repo experiment run --spec experiment.json
```

Inspect:

```bash
uv run --project packages/cli repo experiment list --repo owner/name
uv run --project packages/cli repo experiment show --repo owner/name --run-id <run_id>
uv run --project packages/cli repo experiment explain --repo owner/name --run-id <run_id> --pr 123
uv run --project packages/cli repo artifacts list --repo owner/name --run-id <run_id>
uv run --project packages/cli repo artifacts show --repo owner/name --run-id <run_id> --artifact-id <artifact_id>
```

Backfill semantic cache:

```bash
uv run --project packages/cli repo backfill semantic --repo owner/name --prompt reviewer_rerank --since 2026-01-01T00:00:00Z --dry-run
```

Compare:

```bash
uv run --project packages/cli repo experiment diff --repo owner/name --run-a <a> --run-b <b>
uv run --project packages/cli repo experiment compare --repo owner/name --run-a <a> --run-b <b>
```

Direct evaluation run (debugging):

```bash
uv run --project packages/cli repo evaluation run --repo owner/name --router mentions --pr 123 --run-id debug
```

### 12.2 Pseudocode for one representative routing+eval run

This pseudocode mirrors the actual orchestration structure without requiring you to read source.

```python
cfg = {
  repo: "owner/name",
  data_dir: "data",
  run_id: compute_run_id(cfg_without_run_id),
  routers: [RouterSpec(...), ...],
  cutoff_policy: "created_at",
  truth_policies: ["first_approval_v1", ...],
  strict_streaming_eval: True,
  top_k: 5,
}

pr_numbers = select_prs(cfg)               # from cohort lock or sampling window
cutoffs = {pr: cutoff_for_pr(pr, policy)} # per PR

assert max(cutoffs.values()) <= db_event_horizon if strict

write(manifest.json, {cfg, pr_numbers, cutoffs, router_specs, truth_policy_hashes})

for pr in pr_numbers_sorted_by(cutoff, pr_number):
  snapshot = build_snapshot(repo, pr, cutoff, history.sqlite)
  write(prs/pr/snapshot.json, snapshot)

  inputs = build_inputs_bundle(snapshot, history.sqlite, pinned_artifacts)
  write(prs/pr/inputs.json, inputs)

  truth_by_policy = {}
  for policy in truth_policies:
    truth_by_policy[policy] = truth(policy, repo, pr, cutoff, history.sqlite)

  gates = compute_gate_metrics(repo, pr, cutoff, history.sqlite)

  per_router_block = {}
  for router_id, router in routers:
    result = router.route(repo=repo, pr_number=pr, as_of=cutoff, data_dir=data_dir, top_k=top_k, input_bundle=inputs)
    write(prs/pr/routes/{router_id}.json, {kind:"route_result", version:"v1", router_id, result, meta:{...}})

    routing_metrics = routing_agreement(result, truth_by_policy[primary_policy])
    queue_metrics = queue_metrics(result, ...)
    per_router_block[router_id] = {route_result: result, routing_agreement: routing_metrics, queue: queue_metrics, ...}

  append(per_pr.jsonl, {
    repo, run_id, pr_number, cutoff,
    truth: truth_by_policy,
    gates,
    routers: per_router_block,
  })

report = aggregate(per_pr.jsonl)
write(report.json, report)
write(report.md, render_markdown(report))
```

### 12.3 “What not to do” anti-patterns

- Do not make network calls from routers or evaluation; it breaks determinism and cutoff safety.
- Do not read from a mutable git checkout to compute features; use pinned artifacts keyed by a SHA.
- Do not change `router_id` derivation casually; it breaks artifact paths, report keys, and comparisons.
- Do not add large payloads into `per_pr.jsonl`; store them as separate artifacts and reference paths/hashes.
- Do not treat truth-unavailable rows as “negative examples” without slicing; they are often data-quality artifacts.

### 12.4 Open questions (optional, for maintainers)

- `truth_behavior` naming: it is legacy naming but still emitted; should it be renamed (with a version bump) to avoid confusion?
- Path contract duplication: should evaluation and inference share one authoritative path module to prevent drift?
- Router provenance normalization: which fields belong in `meta` vs `router_feature_meta` vs evidence?
