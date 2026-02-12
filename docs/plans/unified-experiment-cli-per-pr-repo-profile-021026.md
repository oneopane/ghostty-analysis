# Task: Repo-wide architecture audit + unified experiment CLI + per-PR repo-profile integration

You are a coding agent operating inside this Python `uv` workspace monorepo. Your job is to:
1) audit the current codebase to confirm the described architecture matches reality (and identify divergences),
2) propose a concrete, minimal, testable design update that enables **per-PR, cutoff-safe “repo profile” artifacts**,
3) implement the update with strong determinism, provenance, and evaluation compatibility,
4) **package the entire experimentation workflow inside a single CLI tool** that supports: setup/new experiment, cohort creation, running evals, diffs, explain, and profile preflight.

Be skeptical: treat the provided architectural summary as a hypothesis to verify, not ground truth.

---

## Context (what this repo is trying to prove)

We are building a proof-of-concept that for open-source repos we can run maintainer-useful tasks (reviewer routing, later risk/intent/explanations) **offline**, **cutoff-safe**, and **leakage-aware**, with **deterministic artifacts** and **reproducible evaluation**.

Existing “spine” (verify this):
GitHub ingestion → normalized SQLite history → cutoff-safe PR snapshots → routing → evaluation.

We want to add a missing abstraction:
**Repo Profile (per PR)**: a stage that scans *pinned repo artifacts* (CODEOWNERS/OWNERS/teams.yml/CONTRIBUTING/label semantics/etc.), compiles them into canonical intermediate representations (IR), versions them by SHA/cutoff, and stores them as deterministic artifacts. Downstream routers consume the IR deterministically.

LLMs may be involved, but must be restricted to:
- Builder/Compiler role: (pinned repo artifacts → strict JSON IR with provenance)
- Decider role: (PRInputBundle + IR → RouteResult), with NO repo scanning at eval time

This task focuses on adding the **Repo Profile builder/IR + plumbing + unified UX CLI**, not on building a fancy LLM decider.

---

## Phase 0 — Fast repo audit (must do first)

### 0.1 Confirm workspace structure and key entrypoints
Verify these exist and align:
- packages/ingestion (CLI: gh_history_ingestion.cli.app:app)
- packages/inference (CLI: repo_routing.cli.app:app)
- packages/evaluation (CLI: evaluation_harness.cli.app:app)
- packages/cli (CLI: repo_cli.cli:app)

Verify dependency edges (evaluation depends on inference) and how `cli` currently mounts other CLIs.

### 0.2 Confirm current “single CLI” reality
Check whether `cli` is already the intended unified front door:
- How it wires/mounts ingestion/inference/evaluation commands today
- Whether it is stable enough to become the *only* supported experiment UX CLI

Goal: decide whether to extend `cli` or replace it with a new “experiments” CLI package. Default preference: extend `cli` unless it is structurally wrong.

### 0.3 Confirm deterministic, offline data substrate
Verify DB paths, eval artifact paths, and deterministic writers:
- data/github/<owner>/<repo>/history.sqlite
- eval outputs under data/github/<owner>/<repo>/eval/<run_id>/

### 0.4 Confirm cutoff-safe reads + leakage guardrails
Verify:
- as-of PR snapshot uses interval tables
- strict stale-cutoff guard exists and tests cover it
- output artifact writer is deterministic

### 0.5 Confirm current gap: truth coverage ambiguity
Inspect evaluation truth extraction and runner output:
- how “truth missing” is represented
- where ingestion gaps / qa reports exist
Report whether eval can distinguish “true no response” vs “truth missing due to ingestion gaps” (expected: no).

### 0.6 Summarize audit findings
Produce a concise report:
- Confirmed items
- Divergences / stale assumptions
- Risks relevant to unified CLI + repo-profile

Stop after Phase 0 and present findings + proposed plan before coding large changes.

---

## Phase 1 — Unified Experiment CLI design (single tool)

### 1.1 Core principle: one CLI to rule experiments
There must be exactly one recommended UX CLI for all experimentation tasks. It should:
- create or scaffold new experiments
- create/lock cohorts deterministically
- run evals (including per-PR repo-profile build)
- show reports, explain PRs, list runs
- diff runs (on identical cohort)
- run “doctor/preflight” checks (DB horizon, ingestion gaps overlap, CODEOWNERS coverage, profile coverage)
- optionally trigger ingestion flows (or at least link to them cleanly)

### 1.2 Command surface (proposed)
Implement under `repo` (cli) unless audit suggests otherwise. Propose a structure like:

- `repo ingest ...` (existing)
- `repo cohort create ...` (new; outputs cohort.json with hash)
- `repo experiment init ...` (new; writes an ExperimentSpec template)
- `repo experiment run ...` (new; runs evaluation using a spec + cohort; builds per-PR repo profile by default)
- `repo experiment show ...` (wrap evaluation show)
- `repo experiment explain ...` (wrap evaluation explain)
- `repo experiment list ...` (wrap evaluation list)
- `repo experiment diff ...` (new; compares two run_ids; requires same cohort hash unless `--force`)
- `repo doctor ...` (new; preflight checks + coverage summary)
- `repo profile build ...` (optional; build repo profile for PR(s) without running eval)

Keep the underlying packages (ingestion/inference/evaluation) as libraries; the unified CLI is a thin orchestration + UX layer.

### 1.3 ExperimentSpec + Cohort as first-class artifacts
Define file formats (v1):
- `cohort.json`:
  - repo, time bounds, filters, seed, limit, list of PRs, per-PR cutoff timestamps (optional), hash
- `experiment.json` (ExperimentSpec):
  - repo, cohort reference (path or hash), cutoff policy, truth window, strictness
  - routers (builtin ids + import-paths) and router configs
  - repo-profile build settings
  - feature policy mode
  - tags/notes
- Both must be hashed; run manifests should record both hashes.

The unified CLI should accept either:
- `--cohort cohort.json` and `--spec experiment.json`, OR
- inline args for quick runs (but must still emit a spec into the run dir for reproducibility).

### 1.4 Compatibility + migration
- Preserve existing entrypoints for now (ingestion, inference, evaluation) but treat them as “advanced” tools.
- The new unified CLI should call them internally or invoke their library functions directly.
- Do not break existing behavior; add new commands and route users to `repo ...` as the primary workflow.

Deliverable: a design note describing the CLI surface and how it maps to existing code.

---

## Phase 2 — Repo Profile design (per PR, cutoff-safe)

### 2.1 Core requirement
For each PR evaluated at cutoff, create a **RepoProfile** artifact that is:
- anchored to pinned repo state: `base_sha` (per PR),
- built deterministically from pinned inputs,
- stored under the run directory with stable schemas and provenance,
- consumed by routers without any repo scanning at eval time.

### 2.2 Minimal canonical IR objects (v1)
Propose strict JSON schemas (Pydantic models) for:
- RepoProfileIdentity:
  - owner, repo, pr_number, cutoff, base_sha (anchor), schema_version, builder_version
- RepoArtifactManifest (per PR):
  - list of files considered, each with: path, content_hash/blob_sha, source (pinned), size, detected_type
- OwnershipGraph (v1):
  - nodes (person/team/alias), edges (OWNS(path_glob), MAINTAINS(area), MEMBER_OF(team? optional)), each with provenance + confidence
- AreaModel (v1):
  - bounded-size areas list including unknown/other; mappings: path_globs, labels, keywords; provenance
- PolicySignals (v1):
  - small set of routing-relevant process signals; provenance
- RepoVocabulary (v1):
  - mapping label semantics / template fields / keywords → canonical intents & gates; provenance
- RepoProfileQAReport (v1):
  - coverage summary, confidence distribution, warnings, missing critical artifacts

All fields must support “unknown” and must not hallucinate without provenance.

### 2.3 Pinned artifact fetching and storage
Inspect current code for any mechanism like:
- data/.../codeowners/<base_sha>/CODEOWNERS
and determine if a generalized pinned fetch exists.

If missing, implement a minimal, generalized “pinned repo file fetcher” (allowlist) in ingestion:
- fetch file contents by `base_sha` using GitHub API (only during ingestion/build steps, not during eval unless explicitly allowed)
- store under: data/github/<owner>/<repo>/repo_artifacts/<base_sha>/...
- write a manifest with content hashes
- ensure deterministic normalization (newline normalization, stable encoding) before hashing

Define whether eval-time is allowed to fetch missing pinned artifacts:
- Default: NO in strict mode (fail with clear message)
- Optional: `--allow-fetch-missing-artifacts` in unified CLI for convenience (should record that it did network IO)

### 2.4 Determinism + caching contract
- Builder must be idempotent: same pinned inputs → identical outputs
- Content-address artifacts and include hashes in manifests
- If any LLM compile is added:
  - cache by (model_id, prompt_version, input_hash)
  - force stable settings
  - write prompt + model metadata into run dir

Prefer v1 that works without LLM: parse CODEOWNERS deterministically + simple heuristics; LLM compiler can be optional plugin.

---

## Phase 3 — Implementation (end-to-end)

### 3.1 Extend unified CLI (cli) as the front door
Implement new Typer command groups per the Phase 1 spec.
Where possible, call library functions directly rather than shelling out.

Add:
- cohort creation (deterministic)
- experiment init (writes spec template)
- experiment run (wraps evaluation run, builds repo profiles)
- experiment diff (new)
- doctor/preflight (new)
- profile build (optional)

### 3.2 Add Repo Profile module(s)
Likely in inference (routing consumes it):
- `repo_routing/repo_profile/models.py`
- `repo_routing/repo_profile/builder.py`
- `repo_routing/repo_profile/parsers/codeowners.py`
- `repo_routing/repo_profile/storage.py` (stable paths, deterministic writes)

### 3.3 Wire into evaluation runner via unified CLI
In `evaluation_harness.runner.run_streaming_eval` (or via wrapper in cli if preferable):
- before routing each PR:
  - determine base_sha anchor from PR snapshot
  - ensure pinned repo artifacts exist (strict mode fails)
  - build RepoProfile from pinned artifacts
  - write RepoProfile + QA report into run dir per PR
- pass RepoProfile context to routers (or make it available through PRInputBundle / context provider)
- include profile QA summary in per_pr.jsonl

### 3.4 Router consumption contract
Maintain backward compatibility:
- Either extend router interface to accept optional context,
- Or store profile path in PRInputBundle artifacts and allow routers to load it via a helper.
Do not break existing routers.

### 3.5 Tests
Add tests for:
- unified CLI commands (at least smoke tests via Typer runner)
- cohort determinism (same args → same cohort hash + list)
- RepoProfile determinism (same pinned inputs → identical JSON bytes)
- runner writes profile artifacts + includes coverage in per_pr.jsonl
- strict mode failure if pinned artifacts missing
- diff requires identical cohort hash (unless `--force`)

Follow existing pytest patterns and repository conventions.

---

## Non-goals
- Do NOT build a full LLM-based router in this change.
- Do NOT introduce nondeterministic calls during evaluation by default.
- Do NOT remove existing CLIs; unify UX through cli and keep others available.

---

## Output expectations
At the end, produce:
1) Audit report (Phase 0) with divergences and risks
2) Unified CLI design + mapping to underlying packages
3) Implemented code + tests passing
4) Updated runbook snippets showing:
   - `repo cohort create ...`
   - `repo experiment init ...`
   - `repo experiment run ...`
   - `repo experiment diff ...`
   - where RepoProfile artifacts live

Proceed now.
