## Steward Routing + Policy (Offline) Implementation Plan

Goal: implement all algorithmic/offline pieces so the only remaining work is GitHub App integration (webhooks + comment/label application).

Non-goals (for this plan): build the GitHub App, deploy a webhook server, or post comments/labels.

### Design Principles

- Strict layering:
  - `repo-ingestion`: online (GitHub API) -> canonical `history.sqlite`
  - `repo-routing`: offline intelligence (exports, features, routing, receipts)
  - `evaluation-harness`: offline scoring (hit@k/MRR + gate correlation + queue metrics)
- Deterministic + reproducible:
  - All offline logic reads only `history.sqlite` and optional derived artifacts.
  - Derived artifacts are safe to delete and rebuild.
- Experimentation-friendly:
  - Iterate quickly in marimo on derived exports.
  - Promote stable primitives into `repo-routing`.
  - Connect notebook experimentation and production-ish routing via:
    - versioned exports (Parquet)
    - versioned router config (JSON)

---

## Current State (as of 2026-01-28)

Already present:

- Ingestion produces `data/github/<owner>/<repo>/history.sqlite` and interval tables.
- Offline snapshot access:
  - `repo_routing.history.HistoryReader.pull_request_snapshot(number, as_of)`
  - PR snapshot includes `changed_files` (from `pull_request_files`) and review requests.
- Router interface + baselines:
  - `repo_routing.router.base.Router` -> `RouteResult`
  - baselines: `mentions`, `popularity`, `codeowners`
- Gate parsing (offline):
  - `repo_routing.parsing.gates.parse_gate_fields(pr.body)` extracts:
    - issue reference
    - AI disclosure
    - provenance

Missing (this plan):

- A marimo-friendly **export pipeline** (raw fact tables derived from `history.sqlite`).
- Config-driven scoring + a real “stewards” router.
- Receipt rendering + label suggestions (offline outputs).

---

## Progress

Update these checkboxes as work lands.

### Phase 1 — Export foundations (library)
- [ ] Implement `repo_routing.exports.area` (default area + overrides)
- [ ] Implement export extractors (DB → rows) for:
  - [ ] `prs.parquet` (dehydrated PR snapshot)
  - [ ] `prs_text.parquet` (optional; `--include-text`)
  - [ ] `pr_files.parquet`
  - [ ] `pr_activity.parquet` (repo-wide window)
  - [ ] `truth_behavior.parquet` (optional)
  - [ ] `truth_intent.parquet` (optional)
- [ ] Unit tests for export foundations (area mapping + deterministic extraction)

### Phase 2 — Export scripts (experiments)
- [ ] Create `experiments/` workspace structure (`extract/`, `configs/`, `lib/`, `marimo/`)
- [ ] Implement `experiments/extract/export_v0.py` CLI per the pinned contract
- [ ] Add an `export_manifest.json` describing window/version inputs

### Phase 3 — Stewards router (DB-native) + evaluation integration
- [ ] Add scoring config models + loader (strict validation)
- [ ] Implement decay + activity aggregation utilities
- [ ] Implement `repo_routing.router.stewards.StewardsRouter`
- [ ] Add `confidence` to `RouteResult` schema (and propagate through artifacts/eval)
- [ ] Wire evaluation harness to evaluate `stewards` router (bridge → end-state)
- [ ] Unit tests for router/scoring

### Phase 4 — Receipts + labels
- [ ] Implement `suggest_labels(AnalysisResult)`
- [ ] Implement receipt renderer (one-screen markdown)
- [ ] Snapshot/golden tests for receipts

---

## Pinned v0 Decisions (to remove ambiguity)

These are the decisions we will implement unless explicitly changed.

### v0.1: Export-first (“Option 1”)

We will start by exporting **raw-ish fact tables** (Parquet) that are easy to explore in marimo.

- Exports are derived from `history.sqlite`.
- Exports may include **both pre-cutoff and post-cutoff** events; leakage safety is enforced by:
  - every PR row includes its `cutoff` timestamp
  - downstream feature logic must filter events `occurred_at <= cutoff` for model inputs
  - truth labels are explicitly defined as post-cutoff outcomes.

### v0.2: Cutoff policy for exports

- Default cutoff policy: `created_at`.
- Export scripts accept `--cutoff-policy`:
  - `created_at` (default)
  - `ready_for_review` (if present in intervals/events; optional)
  - `created_at_plus_minutes:<int>`

### v0.3: Default area derivation (only for convenience columns)

Exports will include both:
- the raw file `path`
- a convenience `default_area` computed as:
  - first path segment (`src/foo.py` -> `src`)
  - root files (`README.md`) -> `__root__`

Notebook experiments are free to ignore `default_area` and define richer area logic.

### v0.4: Determinism requirements

- Stable row ordering before writing Parquet.
- Stable tie-breaks for any ranking (lexicographic on login).
- All timestamps normalized to ISO-8601 with timezone (`Z`) in Parquet.

### v0.5: Dehydrated vs hydrated exports (PR text)

- Default exports are **dehydrated**: they do **not** include PR `title`/`body`.
- If `--include-text` is provided, exporters additionally write `prs_text.parquet`.
  - This keeps the default dataset smaller and avoids accidental propagation of large text blobs.
  - Notebook experiments that need text (e.g. NLP) can opt in.

### v0.6: Repo-wide activity facts

- `pr_activity.parquet` is exported **repo-wide** over the chosen activity time window.
  - It is not restricted to PRs in `prs.parquet`.
  - This enables computing global reviewer stats / candidate pools from the export alone.

### v0.7: Activity window (pinned)

- Exporters compute the activity window from the selected PR cutoffs:
  - `activity_start = min(cutoff) - activity_lookback_days`
  - `activity_end = max(cutoff) + truth_window`
- `activity_lookback_days` default: **180** (matches evaluation defaults).
- Export scripts accept `--activity-lookback-days` to override.

### v0.8: Activity-to-area attribution (v0 simplification)

- For v0, attributing activity to “areas” is done by joining activity to a PR’s cutoff snapshot file list (`pr_files.parquet` for that PR/cutoff).
- We accept that this is an approximation (not the exact diff at activity time).

### v0.9: Truth definition (for exports)

- Behavior truth (primary): first eligible review submission **after** cutoff.
  - eligible = non-bot, non-author.
- Intent truth (secondary): requested reviewers/teams whose request event occurred in
  `[cutoff, cutoff + intent_window]` where `intent_window` defaults to 60 minutes.

(These truth exports are for analysis; evaluation harness may still evolve independently.)

---

## Pinned Phase 3 Decisions (Router + Scoring + Receipts)

These decisions lock down the “production-ish” offline router behavior.

### P3.1 Router data source (DB-native)

- The `stewards` router reads **only** `history.sqlite` (via `HistoryReader` / SQL), not Parquet exports.
- Parquet exports are for marimo experimentation only and are safe to delete/rebuild.

### P3.2 Candidate pool (v0 = users only)

- Candidates are **users only** in v0 (no teams).
- Default pool: distinct users observed reviewing or commenting in the last `candidate_lookback_days` (default **180**) as-of cutoff.
- Filters (default): exclude bots and exclude PR author.

### P3.3 Areas (v0 staged)

- v0 routing starts with `default_area_for_path(path)`.
- Repo-specific area mapping is supported via an overrides file:
  - `data/github/<owner>/<repo>/routing/area_overrides.json`
  - (glob rules; first match wins)

### P3.4 Activity signals and weights

- Activity types used for stats/scoring:
  - `review_submitted`
  - `comment_created`
  - `review_comment_created`
- v0 default per-event weights (configurable):
  - review_submitted: **1.0**
  - review_comment_created: **0.4**
  - comment_created: **0.2**

### P3.5 Decay defaults

- v0 uses exponential decay + a hard lookback cap:
  - `half_life_days` default: **30**
  - `lookback_days` default: **180**

### P3.6 Scoring model (v0 linear)

- v0 scoring is a weighted sum over candidate features.
- JSON config is versioned and strictly validated.

#### P3.6.1 Scoring config schema (pinned, v0)

Config file path is provided to the router (e.g. `--config experiments/configs/v0.json`).

Pinned keys (v0):

- `version`: string (e.g. `"v0"`)
- `feature_version`: string (e.g. `"v0"`)
- `candidate_pool`:
  - `lookback_days`: int (default 180)
  - `exclude_author`: bool (default true)
  - `exclude_bots`: bool (default true)
- `decay`:
  - `half_life_days`: float (default 30)
  - `lookback_days`: int (default 180)
- `event_weights` (floats):
  - `review_submitted`
  - `review_comment_created`
  - `comment_created`
- `weights` (floats): feature weights for the linear scorer (see P3.6.2)
- `filters`:
  - `min_activity_total`: float (default 0.0)
- `thresholds`:
  - `confidence_high_margin`: float
  - `confidence_med_margin`: float
- `labels`:
  - `include_area_labels`: bool (default false)

Example config (v0):

```json
{
  "version": "v0",
  "feature_version": "v0",
  "candidate_pool": {
    "lookback_days": 180,
    "exclude_author": true,
    "exclude_bots": true
  },
  "decay": {
    "half_life_days": 30,
    "lookback_days": 180
  },
  "event_weights": {
    "review_submitted": 1.0,
    "review_comment_created": 0.4,
    "comment_created": 0.2
  },
  "weights": {
    "area_overlap_activity": 1.0,
    "activity_total": 0.2
  },
  "filters": {
    "min_activity_total": 0.0
  },
  "thresholds": {
    "confidence_high_margin": 0.15,
    "confidence_med_margin": 0.05
  },
  "labels": {
    "include_area_labels": false
  }
}
```

#### P3.6.2 Feature definitions (pinned, v0)

All features are computed strictly from offline history as-of cutoff.

Per candidate (for a given PR at cutoff):

- `activity_total`: decayed weighted sum of candidate activity events in the lookback window.
  - includes `review_submitted`, `review_comment_created`, `comment_created`
  - each event contributes: `event_weight[kind] * decay_weight(age_days)`

- `area_overlap_activity`: decayed weighted sum of candidate activity events where the *historical PR* touched at least one area in common with the current PR’s areas.
  - current PR areas are derived from changed files as-of cutoff.
  - historical PR areas use the repo’s area mapping over that PR’s changed files (v0: `default_area_for_path` + overrides).

Linear score (v0):

- `score = Σ weights[feature] * feature_value`
- candidates are filtered out if `activity_total < filters.min_activity_total`
- sorting / tie-break:
  1) `score` desc
  2) `candidate_login` asc (case-insensitive)

Confidence heuristic (v0):

- Let `s1` and `s2` be top two candidate scores (missing -> 0).
- `margin = s1 - s2`.
  - if `margin >= confidence_high_margin`: `high`
  - else if `margin >= confidence_med_margin`: `medium`
  - else: `low`

### P3.7 Confidence vs risk (two separate concepts)

- `confidence` = how strong the routing recommendation is (high/med/low).
- `risk` = operational/policy risk of the PR (high/med/low), derived primarily from gate fields and “no candidates/areas” conditions.

Pinned risk heuristic (v0):

- `high` if any of:
  - gate fields missing (issue/AI disclosure/provenance)
  - no changed files / no areas detected
  - no candidates after filtering
- else `medium`

Pinned schema change:
- Add `confidence: str = "unknown"` to `repo_routing.router.base.RouteResult` (alongside `risk`).

### P3.8 Evidence contract (structured, not raw events)

- Routers must emit structured evidence sufficient to explain *why* a candidate was ranked.
- Evidence should be small/deterministic; do not embed raw timelines.
- Standard evidence kinds (v0):
  - `activity_totals`
  - `area_overlap`
  - `decay_params`
  - `filters_applied`

### P3.9 Labels and receipts

- v0 labels include gate-derived labels + routing-derived labels:
  - `needs-issue-link`, `needs-ai-disclosure`, `needs-provenance`
  - `routed-high-risk`, `suggested-steward-review`
- Area labels `routed-area:<area>` are behind a config flag (default off).

- Receipt is one-screen markdown, neutral language, no @-mentions by default.

### P3.10 Evaluation harness integration

- Short-term bridge: allow `evaluation-harness` to evaluate `stewards` by treating it like a selectable router/baseline and passing a config path.
- End-state: `repo eval run --router stewards --config ...` (first-class router selection).

### P3.11 Optional caching/artifacts

- Caching derived artifacts (reviewer stats, area maps) is allowed behind an explicit build step (e.g. `repo routing build-artifacts`).
- Router must still be able to run without cache (slower but correct).

---

## Target Architecture (Repository Layout)

### `repo-routing` package code (promotable primitives)

Add these modules under `packages/repo-routing/src/repo_routing/` (phased):

- `exports/` (new, v0)
  - `models.py`: typed schemas for exported rows (optional but recommended)
  - `extract.py`: deterministic extractors from `HistoryReader` / SQL
  - `area.py`: `default_area_for_path(path) -> str`
- `scoring/` (later)
  - `config.py`: scorer config schema + loader
  - `linear.py`: v0 weighted scoring
  - `confidence.py`: High/Med/Low heuristic
  - `risk.py`: HIGH/MED/LOW heuristic
- `analysis/` (later)
  - `models.py`: `AnalysisResult`
  - `engine.py`: `analyze_pr(...) -> AnalysisResult`
- `policy/` (later)
  - `labels.py`: suggested labels (offline)
- `receipt/` (later)
  - `render.py`: one-screen “PR Receipt” markdown
- `router/` (later)
  - `stewards.py`: router that converts `AnalysisResult` into `RouteResult`

### Experimentation workspace (not a package)

Add an experimentation workspace (gitignored outputs):

- `experiments/`
  - `extract/`: export scripts (SQLite -> Parquet)
  - `configs/`: versioned scorer configs (JSON)
  - `lib/`: helpers used by marimo notebooks
  - `marimo/`: notebooks live here

---

## Contracts (Enable Marimo Experimentation)

### 1) Export Dataset Contract (Parquet, v0)

Output location:

- `data/exports/<owner>/<repo>/<export_run_id>/`

The export run id is provided by the caller (`--export-run-id`); exporters do not generate nondeterministic IDs.

#### File: `prs.parquet` (one row per PR)

Minimum columns:
- `repo` (string, `owner/name`)
- `pr_number` (int)
- `cutoff` (timestamp)
- `cutoff_policy` (string)
- `export_version` (string, e.g. `v0`)

Recommended columns:
- `author_login` (string|null)
- `created_at` (timestamp|null)
- `base_sha` (string|null)
- `head_sha` (string|null)
- `n_changed_files` (int)
- gate convenience columns (from PR body as-of cutoff):
  - `missing_issue` (bool)
  - `missing_ai_disclosure` (bool)
  - `missing_provenance` (bool)

#### File: `prs_text.parquet` (optional, one row per PR; written only with `--include-text`)

Minimum columns:
- `repo` (string)
- `pr_number` (int)
- `cutoff` (timestamp)
- `export_version` (string)

Text columns (as-of cutoff):
- `title` (string|null)
- `body` (string|null)

#### File: `pr_files.parquet` (one row per changed file at cutoff)

Minimum columns:
- `repo` (string)
- `pr_number` (int)
- `cutoff` (timestamp)
- `head_sha` (string)
- `path` (string)

Recommended columns:
- `status` (string|null)
- `additions` (int|null)
- `deletions` (int|null)
- `changes` (int|null)
- `default_area` (string)

#### File: `pr_activity.parquet` (one row per PR activity event)

Goal: provide a fact table to compute candidate pools, reviewer stats, and queue metrics.

Minimum columns:
- `repo` (string)
- `pr_number` (int)
- `occurred_at` (timestamp)
- `actor_login` (string)
- `actor_type` (string|null)  *(e.g. `Bot`)*
- `kind` (string enum)

Pinned v0 kinds:
- `review_submitted`
- `comment_created`
- `review_comment_created`

Recommended columns:
- `path` (string|null) *(for review comments when available)*
- `review_state` (string|null)

#### File: `truth_behavior.parquet` (optional, one row per PR)

Minimum columns:
- `repo` (string)
- `pr_number` (int)
- `cutoff` (timestamp)
- `truth_behavior_first_reviewer` (string|null)

Notes:
- `truth_behavior_first_reviewer` is defined as the first eligible review submission **after** cutoff.
- Eligible = non-bot, non-author.

#### File: `truth_intent.parquet` (optional, one row per requested target)

Minimum columns:
- `repo` (string)
- `pr_number` (int)
- `cutoff` (timestamp)
- `requested_at` (timestamp)
- `target_type` (string enum: `user` | `team`)
- `target_name` (string)

Notes:
- Intent truth includes requested reviewers/teams whose request occurred in `[cutoff, cutoff + intent_window]`.
- This normalized shape is preferred over JSON blobs for easy aggregation in marimo.

### 2) Router Config Contract (JSON, v0)

Config is the knob surface area marimo writes and the router reads.

- Stored under: `experiments/configs/*.json`
- Contents (v0, to be finalized in Phase 3):
  - `export_version`/`feature_version`
  - decay parameters
  - weights
  - thresholds
  - filters

---

## Implementation Phases (Updated for Export-first)

### Phase 1: Export Foundations (Library)

Deliverables:

- [ ] `repo_routing.exports.area.default_area_for_path()`
- [ ] Area overrides support (load + apply): `data/github/<owner>/<repo>/routing/area_overrides.json`
- [ ] Extractors that can produce the v0 Parquet tables deterministically:
  - [ ] PR snapshot rows (`prs.parquet`, dehydrated)
  - [ ] PR text rows (`prs_text.parquet`, optional)
  - [ ] changed files rows (`pr_files.parquet`, head_sha as-of cutoff)
  - [ ] repo-wide activity fact rows (`pr_activity.parquet`)
  - [ ] truth behavior rows (`truth_behavior.parquet`, optional)
  - [ ] truth intent rows (`truth_intent.parquet`, optional; normalized)

Acceptance checks:

- [ ] Unit tests for `default_area_for_path`
- [ ] Deterministic extract output on a synthetic fixture DB

### Phase 2: Export Pipeline (Scripts)

Deliverables:

- [ ] `experiments/extract/export_v0.py` (single entrypoint), or split scripts:
  - [ ] `experiments/extract/export_prs.py`
  - [ ] `experiments/extract/export_pr_files.py`
  - [ ] `experiments/extract/export_pr_activity.py`
  - [ ] `experiments/extract/export_truth.py`
- [ ] Write `export_manifest.json` alongside Parquet outputs

CLI requirements (pinned):

- [ ] Runs offline (reads `history.sqlite` only)
- [ ] Accepts:
  - [ ] `--repo owner/name`
  - [ ] `--export-run-id <id>`
  - [ ] `--cutoff-policy ...`
  - [ ] `--from/--start-at` and `--end-at` (created_at window) OR `--pr` list
  - [ ] `--activity-lookback-days` (default: 180)
  - [ ] `--include-text` (optional; writes `prs_text.parquet`)

Acceptance checks:

- [ ] Exports are stable across runs with same inputs
- [ ] Output directory layout matches the contract

### Phase 3: Marimo Loop + Config-driven Scoring

Deliverables:

- [ ] Marimo notebooks under `experiments/marimo/` that:
  - [ ] load Parquet exports
  - [ ] define / evaluate feature recipes
  - [ ] write JSON configs under `experiments/configs/`

- [ ] `repo_routing.scoring` + `repo_routing.router.stewards.StewardsRouter` that:
  - [ ] consumes the JSON config
  - [ ] produces a `RouteResult` with evidence

Acceptance checks:

- [ ] `evaluation-harness run ...` can evaluate `stewards` router outputs (integration work required)

### Phase 4: Receipt + Labels (Offline Outputs)

Deliverables:

- [ ] `repo_routing.policy.labels.suggest_labels(AnalysisResult) -> list[str]`
- [ ] `repo_routing.receipt.render.render_receipt(AnalysisResult) -> str`

Acceptance checks:

- [ ] Snapshot/golden tests for receipt formatting

---

## Open Decisions (need pinning before implementation)

(None for exports v0; remaining decisions are deferred to Phase 3 scoring/receipt semantics.)
