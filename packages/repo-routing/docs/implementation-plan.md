## Steward Routing + Policy (Offline) Implementation Plan

Goal: implement all algorithmic/offline pieces (ingestion already exists) so the only remaining work is GitHub App integration (webhooks + comment/label application).

Non-goals (for this plan): build the GitHub App, deploy a webhook server, or post comments/labels.

### Design Principles

- Strict layering:
  - `repo-ingestion`: online (GitHub API) -> canonical `history.sqlite`
  - `repo-routing`: offline intelligence (features, artifacts, routing, receipts)
  - `evaluation-harness`: offline scoring (hit@k/MRR + gate correlation + queue metrics)
- Deterministic + reproducible:
  - All offline logic reads only `history.sqlite` and optional derived artifacts.
  - Derived artifacts are safe to delete and rebuild.
- Experimentation-friendly:
  - Promote stable feature primitives into `repo-routing`.
  - Keep iteration (weight tuning, new heuristics, visualization) in marimo.
  - Connect them via a versioned export + config contract.

---

## Current State

Already present:

- Ingestion:
  - `gh-history-ingestion pull-requests --with-truth --from ... --end-at ...`
  - produces `data/github/<owner>/<repo>/history.sqlite`
- Offline snapshot access:
  - `repo_routing.history.HistoryReader` supports `pull_request_snapshot(number, as_of)`
  - interval tables exist to reconstruct PR/issue content as-of a timestamp
- Router interface + baselines:
  - `repo_routing.router.base.Router` -> `RouteResult`
  - baselines: `mentions`, `popularity`, `codeowners`
- Gate parsing (offline):
  - `repo_routing.parsing.gates.parse_gate_fields(pr.body)` extracts:
    - issue reference
    - AI disclosure
    - provenance

Missing:

- Area mapping (`area_map`) + derived artifacts
- Time-decayed reviewer stats per area
- A “steward routing” router (not just baselines)
- Receipt rendering + label suggestions (offline outputs)
- Experiment/export pipeline designed for marimo iteration

---

## Target Architecture (Repository Layout)

Add these modules under `packages/repo-routing/src/repo_routing/`:

- `areas/`
  - `models.py`: AreaRule / AreaMap
  - `area_map.py`: derive v0 map from paths + apply overrides
- `signals/`
  - `decay.py`: exponential decay utilities (half-life, etc.)
  - `reviewer_stats.py`: build area->reviewer decayed counts from history
- `features/`
  - `models.py`: `PRFeatures`, `CandidateFeatures` (+ version identifiers)
  - `extract.py`: deterministic feature extraction from `HistoryReader`
- `scoring/`
  - `config.py`: scorer config schema + loader
  - `linear.py`: v0 weighted scoring
  - `confidence.py`: High/Med/Low heuristic
  - `risk.py`: HIGH/MED/LOW heuristic
- `analysis/`
  - `models.py`: `AnalysisResult` (gates, areas, stewards, confidence, risk, reasons, suggested_labels)
  - `engine.py`: `analyze_pr(...) -> AnalysisResult`
- `policy/`
  - `labels.py`: produces suggested labels (no GitHub calls)
- `receipt/`
  - `render.py`: renders a one-screen “PR Receipt” markdown from `AnalysisResult`
- `router/`
  - `stewards.py`: router implementation that converts `AnalysisResult` into `RouteResult`

Add an experimentation workspace (not a package):

- `experiments/`
  - `extract/`: export scripts (SQLite -> Parquet)
  - `configs/`: versioned scorer configs
  - `lib/`: helpers used by marimo notebooks (load exports, write configs)
  - `marimo/`: notebooks live here (not part of this plan’s implementation)

---

## Contracts (These Enable Marimo Experimentation)

### 1) Export Dataset Contract (Parquet)

Exports are derived from `history.sqlite` and meant for fast iteration.

- Output location:
  - `data/exports/<owner>/<repo>/<export_run_id>/` (gitignored)
- Files (v0):
  - `pr_features.parquet` (one row per PR)
  - `candidate_features.parquet` (one row per (pr, candidate))
- Required columns (minimum):
  - common: `repo`, `pr_number`, `as_of`, `feature_version`, `export_version`
  - PR: `author`, `created_at`, `merged_at`, `closed_at`, `merged`, `n_changed_files`, `areas_touched`
  - candidate: `candidate_login`, `area_overlap_score`, `recent_review_count`, `recent_comment_count`, ...
  - truth: `truth_reviewer_login` (when available) to support supervised metrics/diagnostics

### 2) Scorer Config Contract (JSON)

Config is the “knob surface area” marimo writes and the router reads.

- Stored under: `experiments/configs/*.json` (versioned)
- Contents (v0):
  - `feature_version`: string
  - `decay`: parameters (e.g. half-life days)
  - `weights`: mapping from feature name -> float
  - `thresholds`: confidence/risk thresholds
  - `filters`: exclude author, exclude bots, min history requirements

---

## Implementation Phases

### Phase 1: Feature Primitives (Library)

Deliverables:

- `area_map`:
  - v0 auto-derive: top-level directory grouping (`src/`, `docs/`, etc.)
  - optional overrides file per repo (e.g. `data/github/<owner>/<repo>/routing/area_overrides.json`)
- Time decay utilities (exponential decay)
- Reviewer stats builder:
  - compute decayed counts by area from historical reviews/comments
- Feature extraction:
  - deterministic `extract_pr_features(...)` and `extract_candidate_features(...)`

Acceptance checks:

- Unit tests for:
  - path->area mapping
  - decay math
  - deterministic feature extraction on fixture DB

### Phase 2: Export Pipeline (Experiment Interface)

Deliverables:

- `experiments/extract/export_pr_features.py`
- `experiments/extract/export_candidate_features.py`
- (optional) `experiments/extract/export_truth.py`

Acceptance checks:

- Exports run entirely offline (read `history.sqlite` only).
- Exports include version metadata and are stable across runs with same inputs.

### Phase 3: Config-Driven Scoring + Steward Router

Deliverables:

- `repo_routing.scoring`:
  - load + validate JSON config
  - weighted scoring v0
  - confidence + risk heuristics
- `repo_routing.analysis.engine.analyze_pr(...)`:
  - returns stewards (top 1-3) with reasons + evidence
- `repo_routing.router.stewards.StewardsRouter`:
  - converts analysis into `RouteResult` so `evaluation-harness` can score it

Acceptance checks:

- `evaluation-harness run ...` works with the new router and produces reports.
- Evidence is “backed”: paths + historical counts + decay params.

### Phase 4: Receipt + Labels (Offline Outputs)

Deliverables:

- `repo_routing.policy.labels.suggest_labels(AnalysisResult) -> list[str]`
  - includes: `needs-issue-link`, `needs-ai-disclosure`, `needs-provenance`, `routed-high-risk`, `suggested-steward-review`
  - optional: `routed-area:<area>` behind a config flag
- `repo_routing.receipt.render.render_receipt(AnalysisResult) -> str`
  - one-screen format
  - default no @-mentions
  - neutral language

Acceptance checks:

- Snapshot/golden tests for receipt formatting.

---

## How Marimo Fits (Yes, This Is “Correct” Marimo Usage)

Marimo is used as an interactive *client* of the offline contracts:

- Inputs marimo reads:
  - Parquet exports from `data/exports/...`
  - JSON configs from `experiments/configs/...`
- Outputs marimo writes:
  - updated scorer configs (`experiments/configs/...`)
  - optional plots/tables under `experiments/out/...` (gitignored)

Marimo does not:

- import GitHub clients
- read from live GitHub
- mutate `history.sqlite`

This keeps experimentation fast (dataframes in memory) while ensuring the production router remains deterministic and testable.

---

## CLI Expectations (End State)

Offline, deterministic commands we want:

- Build exports:
  - `uv run python experiments/extract/export_pr_features.py --repo owner/name --from ... --end-at ...`
- Route a single PR (using config):
  - `repo routing route --router stewards --repo owner/name --pr 123 --as-of ... --config experiments/configs/v0.json`
- Render receipt (offline):
  - `repo routing receipt --repo owner/name --pr 123 --as-of ... --config ...`
- Evaluate router:
  - `repo eval run --repo owner/name --from ... --end-at ... --limit ... --router stewards --config ...`

---

## Promotion Policy (Experiment -> Product)

- New ideas start in marimo (feature ideas, transformations, weighting).
- When a feature is proven useful:
  - implement it in `repo-routing` as a deterministic extractor
  - add tests
  - bump `feature_version`
  - keep tuned weights as a config file (versioned)
