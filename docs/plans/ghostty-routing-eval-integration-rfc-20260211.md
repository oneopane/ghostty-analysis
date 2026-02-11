# Ghostty Routing/Eval Integration RFC + Implementation Plan (A→B)

**Status:** Active planning / execution tracker  
**Date:** 2026-02-11  
**Owner:** oneopane  
**Scope:** `repo-ingestion`, `repo-routing`, `evaluation-harness`, `repo-cli`  
**Baseline run:** `ghostty-org/ghostty` / `audit-ghostty-20260210-6mo-s4242-r3-v3`

---

## TL;DR

We will implement this in 3 layers:
1. **Fix correctness + generic truth framework** (policy-configurable labels, policy-keyed metrics)
2. **Improve deterministic routing** (`union_v1` + `hybrid_ranker_v1`, ownership signal restoration)
3. **Add constrained LLM reranking** (replay-first, auditable, candidate-whitelist)

This plan is now updated with:
- locked decisions,
- checkboxes for every implementable item,
- explicit **files to touch** and **files to read first** per implementation item.

---

## 1) Objectives and Constraints

Primary objective: **accuracy**.  
Secondary objectives: **reliability** and **time-to-iteration**.

Hard constraints:
- preserve determinism/reproducibility for audit runs,
- no leakage across cutoff,
- policy/denominator semantics must be explicit in artifacts,
- avoid optimizing against unstable labels.

---

## 2) Verified Baseline Context (why this plan exists)

Baseline run (`audit-ghostty-20260210-6mo-s4242-r3-v3`) shows:
- popularity has non-zero signal (MRR ~0.166)
- mentions/codeowners are zeroed in this run
- observed truth coverage is sparse (27/119 observed)

Known blockers found in code/artifacts:
- truth-window config/execution mismatch (`PT1H` configured vs 48h default execution path)
- split CODEOWNERS storage contract (`repo_artifacts/...` vs `codeowners/...` readers)
- merger actor readiness gap in ingestion semantics
- one-policy-like scoring path despite richer policy intent

---

## 3) Strategy and End Outcomes

### Strategy choice: **A → B**
- **A (first):** correctness + generic multi-policy truth + deterministic signal restoration
- **B (second):** deterministic candidate union + constrained LLM rerank
- Defer C (LLM-centric generation) until after B is proven

### End outcomes
- Generic truth engine for arbitrary policies (declarative + plugin)
- Policy-keyed artifacts (`per_pr.jsonl`, `report.json`, manifests)
- Deterministic hybrid baseline materially stronger than popularity
- LLM reranker with replayable/auditable provenance
- Quality gates enforce run health before promotion

---

## 4) Locked Decisions (Approved)

All previously open decisions are now approved and locked.

### 4.1 Policy strategy (locked)
- [x] **Interim primary policy:** `first_approval_v1`
- [x] **Final primary policy target:** `hybrid_owner_v1` (enabled after merger-readiness gate)

### 4.2 Promotion rule (locked)
- [x] Primary promotion KPI: `MRR(primary_policy, observed_and_router_nonempty)`
- [x] Promote only if **all** hold:
  1. absolute uplift `ΔMRR >= +0.015`
  2. 95% bootstrap CI lower bound `> 0`
  3. `n(observed_and_router_nonempty) >= 120`
  4. reliability gates pass
  5. no major guardrail regression (e.g., `hit@1` drop > 1pp)

### 4.3 Audit quality thresholds (locked)
- [x] Truth-window consistency: **100%** (all phases)
- [x] **Phase 1 thresholds**:
  - unknown ingestion-gap rate `<= 3%`
  - codeowners/profile availability `>= 90%` when ownership routers enabled
  - router unavailable rate `<= 2%`
- [x] **Phase 2+ thresholds**:
  - unknown ingestion-gap rate `<= 2%`
  - codeowners/profile availability `>= 95%`
  - router unavailable rate `<= 1%`

### 4.4 LLM mode and migration (locked)
- [x] Audit default LLM mode: `replay` (explicit override needed for `live`)
- [x] Schema migration: **short additive transition**, then hard cut
  - dual read/write for 1–2 run cycles
  - remove legacy fields after migration gate passes

### 4.5 Generic truth framework scope (locked)
- [x] Declarative DSL v1 is **narrow + stable**
- [x] Plugin escape hatch allowed (import-path), with provenance and allowlist constraints
- [x] `target_kind` v1 default scope: **`actor_set`** (class/multilabel later)
- [x] DSL v1 selectors: `first`, `last`, `union`, `priority_chain`
- [x] DSL v1 sources: `reviews`, `review_comments`, `events`, `review_requests`

---

## 5) Generic Truth Framework Contract (Implementation Target)

### 5.1 `TruthPolicySpec` v1
Minimum fields:
- `id`, `version`
- `target_kind` (v1: `actor_set`)
- `window`
- `sources`
- `filters`
- `selector`
- `status_rules`
- optional `fallback_chain`
- optional `params`

### 5.2 `TruthResult` v1
Required output envelope:
- `policy_id`, `policy_version`
- `status` (`observed`, `no_post_cutoff_response`, `unknown_due_to_ingestion_gap`, ...)
- `targets` (typed to `target_kind`)
- `diagnostics` (window bounds, source branch, eligibility counts, data gaps)
- `provenance` (policy hash + engine version)

### 5.3 Execution modes
- Declarative built-ins from registry/spec
- Import-path plugin policies (allowlisted)
- Both must emit the same `TruthResult` shape

### 5.4 Initial built-in policy set
- `first_response_v1`
- `first_approval_v1`
- `merger_v1` (readiness-gated)
- `hybrid_owner_v1`

---

## 6) Implementation Plan (with file touch/read maps)

## Progress Snapshot

| Phase | Scope | Status | Exit gate |
|---|---|---|---|
| Phase 0 | correctness + contract lock | Completed | window consistency + schemas locked |
| Phase 1 | generic truth framework + reporting | Completed | policy-keyed artifacts emitted |
| Phase 2 | ownership restoration + deterministic hybrid | Completed (implementation) | hybrid uplift + quality gates pass |
| Phase 3 | constrained LLM reranking + replayability | Completed (implementation) | replayable uplift over deterministic hybrid |

---

## Phase 0 — Correctness + Contract Lock

### Work items

- [x] **P0.1 Wire configured truth window into execution path**
  - **Touch:**
    - `packages/evaluation-harness/src/evaluation_harness/runner.py`
    - `packages/evaluation-harness/src/evaluation_harness/truth.py`
    - `packages/evaluation-harness/src/evaluation_harness/config.py` (if argument plumbing needed)
  - **Read first:**
    - `packages/evaluation-harness/src/evaluation_harness/config.py`
    - `packages/evaluation-harness/src/evaluation_harness/manifest.py`
    - `packages/evaluation-harness/src/evaluation_harness/truth.py`
    - `packages/evaluation-harness/tests/test_truth_diagnostics.py`

- [x] **P0.2 Add regression tests for configured-vs-effective truth window**
  - **Touch:**
    - `packages/evaluation-harness/tests/test_truth_diagnostics.py`
    - `packages/evaluation-harness/tests/test_end_to_end_run.py`
    - `packages/evaluation-harness/tests/fixtures/build_min_db.py` (if fixture extension required)
  - **Read first:**
    - `packages/evaluation-harness/src/evaluation_harness/runner.py`
    - `packages/evaluation-harness/src/evaluation_harness/manifest.py`
    - `packages/evaluation-harness/src/evaluation_harness/truth.py`

- [x] **P0.3 Clarify first-response semantics (reviews vs review_comments) and align docs/tests**
  - **Touch:**
    - `packages/evaluation-harness/src/evaluation_harness/truth.py`
    - `packages/evaluation-harness/docs/metrics.md`
    - `packages/evaluation-harness/docs/runbook.md`
    - `packages/evaluation-harness/tests/test_truth_diagnostics.py`
  - **Read first:**
    - `packages/evaluation-harness/src/evaluation_harness/truth.py`
    - `packages/evaluation-harness/src/evaluation_harness/reporting/markdown.py`

- [x] **P0.4 Resolve legacy truth config knobs (`behavior_truth_policy`, `intent_truth_from_review_requests`) into new framework path**
  - **Touch:**
    - `packages/evaluation-harness/src/evaluation_harness/config.py`
    - `packages/evaluation-harness/src/evaluation_harness/models.py`
    - `packages/evaluation-harness/src/evaluation_harness/runner.py`
    - `packages/evaluation-harness/src/evaluation_harness/cli/app.py`
    - `packages/evaluation-harness/docs/runbook.md`
  - **Read first:**
    - `packages/evaluation-harness/src/evaluation_harness/truth.py`
    - `packages/evaluation-harness/src/evaluation_harness/config.py`
    - `packages/evaluation-harness/src/evaluation_harness/cli/app.py`

- [x] **P0.5 Lock `TruthPolicySpec` v1 + `TruthResult` v1 schemas and contract tests**
  - **Touch:**
    - `packages/evaluation-harness/src/evaluation_harness/truth_policy.py` *(new)*
    - `packages/evaluation-harness/src/evaluation_harness/truth_schema.py` *(new)*
    - `packages/evaluation-harness/tests/test_truth_policy_contracts.py` *(new)*
    - `packages/evaluation-harness/docs/metrics.md` (contract docs)
  - **Read first:**
    - `packages/evaluation-harness/src/evaluation_harness/models.py`
    - `packages/evaluation-harness/src/evaluation_harness/reporting/models.py`
    - `packages/evaluation-harness/src/evaluation_harness/truth.py`

### Phase 0 exit criteria
- [x] truth-window mismatch rate in tests = 0
- [x] manifest truth config equals effective diagnostics behavior in at least one e2e run
- [x] `TruthPolicySpec`/`TruthResult` schema validation passes for baseline policies

---

## Phase 1 — Generic Truth-Policy Framework + Policy-Keyed Reporting

### Work items

- [x] **P1.1 Implement policy registry + loader + validation (declarative mode)**
  - **Touch:**
    - `packages/evaluation-harness/src/evaluation_harness/truth_policy.py` *(new or expanded)*
    - `packages/evaluation-harness/src/evaluation_harness/config.py`
    - `packages/evaluation-harness/src/evaluation_harness/models.py`
  - **Read first:**
    - `packages/evaluation-harness/src/evaluation_harness/config.py`
    - `packages/evaluation-harness/src/evaluation_harness/models.py`
    - `packages/repo-routing/src/repo_routing/predictor/features/feature_registry.py` (registry pattern reference)

- [x] **P1.2 Add plugin policy adapter (import-path mode) with allowlist/provenance checks**
  - **Touch:**
    - `packages/evaluation-harness/src/evaluation_harness/truth_policy.py`
    - `packages/evaluation-harness/src/evaluation_harness/runner.py`
    - `packages/evaluation-harness/tests/test_truth_policy_plugins.py` *(new)*
  - **Read first:**
    - `packages/evaluation-harness/tests/test_runner_import_router.py`
    - `packages/repo-routing/src/repo_routing/registry.py`

- [x] **P1.3 Implement built-in `first_response_v1` and `first_approval_v1` under generic policy engine**
  - **Touch:**
    - `packages/evaluation-harness/src/evaluation_harness/truth.py`
    - `packages/evaluation-harness/src/evaluation_harness/truth_policy.py`
    - `packages/evaluation-harness/tests/test_truth_diagnostics.py`
  - **Read first:**
    - `packages/evaluation-harness/src/evaluation_harness/db.py`
    - `packages/repo-ingestion/src/gh_history_ingestion/storage/schema.py`
    - `packages/evaluation-harness/tests/test_bot_filtering.py`

- [x] **P1.4 Implement `merger_v1` as readiness-gated policy**
  - **Touch:**
    - `packages/evaluation-harness/src/evaluation_harness/truth.py`
    - `packages/evaluation-harness/src/evaluation_harness/truth_policy.py`
    - `packages/evaluation-harness/src/evaluation_harness/config.py`
    - `packages/evaluation-harness/tests/test_truth_merger_policy.py` *(new)*
  - **Read first:**
    - `packages/repo-ingestion/src/gh_history_ingestion/storage/schema.py`
    - `packages/repo-ingestion/src/gh_history_ingestion/events/normalizers/pull_request.py`
    - `packages/repo-ingestion/src/gh_history_ingestion/storage/upsert.py`

- [ ] **P1.5 Implement `hybrid_owner_v1` priority-chain policy with branch diagnostics**
  - **Touch:**
    - `packages/evaluation-harness/src/evaluation_harness/truth.py`
    - `packages/evaluation-harness/src/evaluation_harness/truth_policy.py`
    - `packages/evaluation-harness/tests/test_truth_hybrid_owner_policy.py` *(new)*
  - **Read first:**
    - `packages/evaluation-harness/src/evaluation_harness/truth.py`
    - `packages/evaluation-harness/tests/test_truth_diagnostics.py`

- [x] **P1.6 Emit policy-keyed truth in `per_pr.jsonl` (versioned)**
  - **Touch:**
    - `packages/evaluation-harness/src/evaluation_harness/runner.py`
    - `packages/evaluation-harness/src/evaluation_harness/models.py`
    - `packages/evaluation-harness/src/evaluation_harness/store/filesystem.py`
    - `packages/evaluation-harness/tests/test_end_to_end_run.py`
  - **Read first:**
    - `packages/evaluation-harness/src/evaluation_harness/store/filesystem.py`
    - `packages/evaluation-harness/src/evaluation_harness/reporting/models.py`
    - `data/github/ghostty-org/ghostty/eval/audit-ghostty-20260210-6mo-s4242-r3-v3/per_pr.jsonl`

- [x] **P1.7 Emit policy-keyed routing metrics + denominator slices in `report.json`**
  - **Touch:**
    - `packages/evaluation-harness/src/evaluation_harness/metrics/routing_agreement.py`
    - `packages/evaluation-harness/src/evaluation_harness/reporting/models.py`
    - `packages/evaluation-harness/src/evaluation_harness/reporting/json.py`
    - `packages/evaluation-harness/tests/test_routing_agreement.py`
  - **Read first:**
    - `packages/evaluation-harness/src/evaluation_harness/metrics/routing_agreement.py`
    - `packages/evaluation-harness/src/evaluation_harness/reporting/models.py`
    - baseline `report.json`

- [x] **P1.8 Extend markdown reporting with policy + denominator sections**
  - **Touch:**
    - `packages/evaluation-harness/src/evaluation_harness/reporting/markdown.py`
    - `packages/evaluation-harness/src/evaluation_harness/reporting/formatters.py`
    - `packages/evaluation-harness/tests/test_end_to_end_run.py`
  - **Read first:**
    - `packages/evaluation-harness/src/evaluation_harness/reporting/markdown.py`
    - `packages/evaluation-harness/docs/metrics.md`

- [x] **P1.9 Add `--policy` support to explain surfaces**
  - **Touch:**
    - `packages/evaluation-harness/src/evaluation_harness/cli/app.py`
    - `packages/repo-cli/src/repo_cli/unified_experiment.py`
    - `packages/repo-cli/src/repo_cli/cli.py`
    - `packages/repo-cli/tests/test_unified_experiment_cli.py`
  - **Read first:**
    - `packages/evaluation-harness/src/evaluation_harness/cli/app.py`
    - `packages/repo-cli/src/repo_cli/unified_experiment.py`

- [x] **P1.10 Add manifest truth-config block (`policies`, `primary`, `effective_window`, `policy_hashes`)**
  - **Touch:**
    - `packages/evaluation-harness/src/evaluation_harness/manifest.py`
    - `packages/evaluation-harness/src/evaluation_harness/runner.py`
    - `packages/repo-cli/src/repo_cli/unified_experiment.py`
    - `packages/evaluation-harness/tests/test_end_to_end_run.py`
  - **Read first:**
    - `packages/evaluation-harness/src/evaluation_harness/manifest.py`
    - `data/.../manifest.json`
    - `data/.../experiment_manifest.json`

### Phase 1 exit criteria
- [x] e2e run emits policy-keyed truth + metrics for at least 2 active policies
- [x] denominator slices present for each `{policy, router}`
- [x] explain command supports policy selection
- [x] declarative + plugin policy paths pass contract tests

---

## Phase 2 — Ownership Signal Restoration + Deterministic Hybrid

### Work items

- [x] **P2.1 Unify CODEOWNERS source-path contract across profile/features/routers**
  - **Touch:**
    - `packages/repo-routing/src/repo_routing/paths.py`
    - `packages/repo-routing/src/repo_routing/router/baselines/codeowners.py`
    - `packages/repo-routing/src/repo_routing/predictor/features/ownership.py`
    - `packages/repo-routing/src/repo_routing/repo_profile/storage.py`
    - `packages/repo-routing/tests/test_codeowners_router_profile_context.py`
    - `packages/repo-routing/tests/test_ownership_features.py`
  - **Read first:**
    - `packages/repo-routing/src/repo_routing/repo_profile/builder.py`
    - `packages/repo-ingestion/src/gh_history_ingestion/repo_artifacts/fetcher.py`

- [x] **P2.2 Add coverage telemetry (presence/degraded/missing critical artifacts)**
  - **Touch:**
    - `packages/repo-routing/src/repo_routing/repo_profile/builder.py`
    - `packages/repo-routing/src/repo_routing/repo_profile/models.py`
    - `packages/evaluation-harness/src/evaluation_harness/runner.py`
    - `packages/evaluation-harness/src/evaluation_harness/reporting/models.py`
    - `packages/evaluation-harness/tests/test_runner_repo_profile.py`
  - **Read first:**
    - `packages/repo-routing/src/repo_routing/repo_profile/models.py`
    - `packages/evaluation-harness/src/evaluation_harness/models.py`

- [x] **P2.3 Enforce audit quality gates in unified experiment run path**
  - **Touch:**
    - `packages/repo-cli/src/repo_cli/unified_experiment.py`
    - `packages/repo-cli/src/repo_cli/cli.py`
    - `packages/repo-cli/tests/test_unified_experiment_cli.py`
    - `packages/repo-cli/README.md`
  - **Read first:**
    - `packages/repo-cli/src/repo_cli/unified_experiment.py`
    - `packages/evaluation-harness/src/evaluation_harness/reporting/models.py`

- [x] **P2.4 Add doctor diagnostics for policy readiness (approval + merger)**
  - **Touch:**
    - `packages/repo-cli/src/repo_cli/unified_experiment.py`
    - `packages/repo-cli/tests/test_unified_experiment_cli.py`
    - `packages/evaluation-harness/src/evaluation_harness/truth.py` (readiness signal helper if needed)
  - **Read first:**
    - `packages/repo-cli/src/repo_cli/unified_experiment.py`
    - `packages/repo-ingestion/src/gh_history_ingestion/storage/schema.py`

- [x] **P2.5 Resolve merger actor readiness (schema/ingestion) OR keep policy gated**
  - **Touch (if implementing readiness):**
    - `packages/repo-ingestion/src/gh_history_ingestion/storage/schema.py`
    - `packages/repo-ingestion/src/gh_history_ingestion/storage/upsert.py`
    - `packages/repo-ingestion/src/gh_history_ingestion/events/normalizers/pull_request.py`
    - `packages/repo-ingestion/src/gh_history_ingestion/ingest/pull_requests.py`
    - `packages/repo-ingestion/tests/test_schema.py`
    - `packages/repo-ingestion/tests/test_events.py`
  - **Read first:**
    - `packages/repo-ingestion/src/gh_history_ingestion/storage/db.py`
    - `packages/repo-ingestion/src/gh_history_ingestion/events/event_record.py`
    - `packages/evaluation-harness/src/evaluation_harness/truth.py`

- [x] **P2.6 Implement `union_v1` candidate-union router (source-preserving evidence)**
  - **Touch:**
    - `packages/repo-routing/src/repo_routing/router/baselines/union.py` *(new)*
    - `packages/repo-routing/src/repo_routing/registry.py`
    - `packages/repo-routing/tests/test_registry_loading.py`
    - `packages/repo-routing/tests/test_union_router.py` *(new)*
  - **Read first:**
    - `packages/repo-routing/src/repo_routing/router/baselines/mentions.py`
    - `packages/repo-routing/src/repo_routing/router/baselines/popularity.py`
    - `packages/repo-routing/src/repo_routing/router/baselines/codeowners.py`
    - `packages/repo-routing/src/repo_routing/router/stewards.py`

- [x] **P2.7 Implement deterministic `hybrid_ranker_v1` over union candidates**
  - **Touch:**
    - `packages/repo-routing/src/repo_routing/router/hybrid_ranker.py` *(new)*
    - `packages/repo-routing/src/repo_routing/registry.py`
    - `packages/repo-routing/src/repo_routing/predictor/feature_extractor_v1.py` (if feature reuse path added)
    - `packages/repo-routing/tests/test_hybrid_ranker.py` *(new)*
  - **Read first:**
    - `packages/repo-routing/src/repo_routing/predictor/feature_extractor_v1.py`
    - `packages/repo-routing/src/repo_routing/predictor/features/feature_registry.py`

- [x] **P2.8 Version/hash deterministic ranker weights artifact**
  - **Touch:**
    - `packages/repo-routing/src/repo_routing/router/hybrid_ranker.py` *(new/expanded)*
    - `packages/repo-routing/src/repo_routing/artifacts/writer.py`
    - `packages/evaluation-harness/src/evaluation_harness/manifest.py`
    - `packages/evaluation-harness/src/evaluation_harness/runner.py`
  - **Read first:**
    - `packages/repo-routing/src/repo_routing/artifacts/writer.py`
    - `packages/repo-cli/src/repo_cli/unified_experiment.py` (hash/provenance pattern)

- [x] **P2.9 Add structured eval comparisons (popularity vs union vs deterministic hybrid)**
  - **Touch:**
    - `packages/repo-cli/src/repo_cli/unified_experiment.py`
    - `packages/repo-cli/tests/test_unified_experiment_cli.py`
    - `scripts/validate_feature_stack.sh` (if adding targeted suite)
  - **Read first:**
    - `packages/repo-cli/src/repo_cli/unified_experiment.py`
    - `packages/evaluation-harness/src/evaluation_harness/metrics/routing_agreement.py`

### Phase 2 exit criteria
- [ ] ownership artifact availability metrics meet Phase 2 thresholds
- [ ] deterministic hybrid beats popularity on primary promotion KPI slice
- [x] audit profile hard-fails on gate violations

---

## Phase 3 — Constrained LLM Reranking + Replayability

### Work items

- [x] **P3.1 Implement `llm_rerank_v1` on top of union candidates only**
  - **Touch:**
    - `packages/repo-routing/src/repo_routing/router/llm_rerank.py` *(new)*
    - `packages/repo-routing/src/repo_routing/registry.py`
    - `packages/repo-routing/tests/test_llm_rerank.py` *(new)*
  - **Read first:**
    - `packages/repo-routing/src/repo_routing/examples/llm_router_example.py`
    - `packages/repo-routing/src/repo_routing/router/base.py`
    - `packages/repo-routing/src/repo_routing/router/baselines/union.py` *(from P2)*

- [x] **P3.2 Enforce structured JSON output + schema validation for LLM responses**
  - **Touch:**
    - `packages/repo-routing/src/repo_routing/router/llm_rerank.py`
    - `packages/repo-routing/src/repo_routing/router/llm_schema.py` *(new)*
    - `packages/repo-routing/tests/test_llm_rerank.py`
  - **Read first:**
    - `packages/repo-routing/src/repo_routing/examples/llm_router_example.py`
    - `packages/evaluation-harness/src/evaluation_harness/truth_schema.py` (schema pattern)

- [x] **P3.3 Require evidence references in LLM output and propagate to per-PR artifacts**
  - **Touch:**
    - `packages/repo-routing/src/repo_routing/router/llm_rerank.py`
    - `packages/evaluation-harness/src/evaluation_harness/runner.py`
    - `packages/evaluation-harness/src/evaluation_harness/models.py`
  - **Read first:**
    - `packages/repo-routing/src/repo_routing/router/explain.py`
    - `packages/evaluation-harness/src/evaluation_harness/models.py`

- [x] **P3.4 Add run modes (`off|live|replay`) with `replay` default in audit profile**
  - **Touch:**
    - `packages/repo-cli/src/repo_cli/unified_experiment.py`
    - `packages/repo-cli/src/repo_cli/cli.py`
    - `packages/evaluation-harness/src/evaluation_harness/config.py`
    - `packages/evaluation-harness/src/evaluation_harness/manifest.py`
    - `packages/repo-cli/tests/test_unified_experiment_cli.py`
  - **Read first:**
    - `packages/repo-cli/src/repo_cli/unified_experiment.py`
    - `packages/evaluation-harness/src/evaluation_harness/config.py`

- [x] **P3.5 Implement replay cache (prompt/model/params/candidates hash key)**
  - **Touch:**
    - `packages/repo-routing/src/repo_routing/predictor/pipeline.py`
    - `packages/repo-routing/src/repo_routing/router/llm_cache.py` *(new)*
    - `packages/repo-routing/tests/test_llm_cache.py` *(new)*
  - **Read first:**
    - `packages/repo-routing/src/repo_routing/predictor/pipeline.py`
    - `packages/repo-routing/src/repo_routing/examples/llm_router_example.py`

- [x] **P3.6 Record LLM provenance hashes in manifests/per-PR outputs**
  - **Touch:**
    - `packages/evaluation-harness/src/evaluation_harness/manifest.py`
    - `packages/evaluation-harness/src/evaluation_harness/runner.py`
    - `packages/evaluation-harness/src/evaluation_harness/reporting/models.py`
    - `packages/evaluation-harness/tests/test_end_to_end_run.py`
  - **Read first:**
    - `packages/evaluation-harness/src/evaluation_harness/manifest.py`
    - existing run manifests/report outputs

- [x] **P3.7 Add cost/latency telemetry to report extras**
  - **Touch:**
    - `packages/evaluation-harness/src/evaluation_harness/reporting/models.py`
    - `packages/evaluation-harness/src/evaluation_harness/reporting/json.py`
    - `packages/evaluation-harness/src/evaluation_harness/reporting/markdown.py`
  - **Read first:**
    - `packages/evaluation-harness/src/evaluation_harness/reporting/models.py`
    - `packages/evaluation-harness/src/evaluation_harness/reporting/markdown.py`

- [x] **P3.8 Add replay reproducibility tests (bit-for-bit outputs where expected)**
  - **Touch:**
    - `packages/repo-routing/tests/test_llm_replay_reproducibility.py` *(new)*
    - `packages/evaluation-harness/tests/test_end_to_end_run.py`
    - `packages/repo-cli/tests/test_unified_experiment_cli.py`
  - **Read first:**
    - `packages/repo-routing/tests/test_registry_loading.py`
    - `packages/evaluation-harness/tests/test_end_to_end_run.py`

### Phase 3 exit criteria
- [ ] LLM reranker beats deterministic hybrid on primary KPI and passes reliability gates
- [x] replay mode reproduces cached outputs deterministically
- [x] audit-mode can run without live network LLM calls

---

## 7) Quality Gates (Implemented policy)

### 7.1 Gate set
- [x] G1: truth-window consistency = 100%
- [x] G2: active truth policy schema validation passes
- [x] G3: unknown ingestion-gap rate within threshold
- [x] G4: ownership artifact availability within threshold
- [x] G5: router unavailable rate within threshold
- [x] G6: deterministic reproducibility checks pass

### 7.2 Threshold schedule (locked)
- [x] Phase 1: `unknown<=3%`, `availability>=90%`, `unavailable<=2%`
- [x] Phase 2+: `unknown<=2%`, `availability>=95%`, `unavailable<=1%`

### 7.3 Gate enforcement implementation
- [x] Enforce gates in `repo experiment run` audit profile
  - **Touch:**
    - `packages/repo-cli/src/repo_cli/unified_experiment.py`
    - `packages/repo-cli/src/repo_cli/cli.py`
    - `packages/repo-cli/tests/test_unified_experiment_cli.py`
  - **Read first:**
    - `packages/evaluation-harness/src/evaluation_harness/reporting/models.py`
    - `packages/evaluation-harness/src/evaluation_harness/manifest.py`

---

## 8) KPI and Promotion Policy (Implemented policy)

### 8.1 Primary KPI (locked)
- [x] `MRR(primary_policy, observed_and_router_nonempty)`

### 8.2 Secondary guardrails
- [x] hit@1/hit@3/hit@5 on same denominator
- [x] reliability gates are hard constraints

### 8.3 Promotion implementation
- [x] Implement promotion evaluator with locked rule thresholds
  - **Touch:**
    - `packages/repo-cli/src/repo_cli/unified_experiment.py`
    - `packages/evaluation-harness/src/evaluation_harness/reporting/models.py`
    - `packages/evaluation-harness/src/evaluation_harness/reporting/json.py`
  - **Read first:**
    - `packages/evaluation-harness/src/evaluation_harness/metrics/routing_agreement.py`
    - baseline run `report.json`

---

## 9) Schema Migration Plan (Additive → Hard Cut)

### Migration steps
- [x] M1: Introduce new policy-keyed fields while retaining legacy fields (dual write)
- [x] M2: Update readers/CLI/reporting to consume new fields (dual read)
- [ ] M3: Run 1–2 cycles with migration health checks
- [ ] M4: Remove legacy fields and compatibility adapters

### File map
- **Touch:**
  - `packages/evaluation-harness/src/evaluation_harness/models.py`
  - `packages/evaluation-harness/src/evaluation_harness/runner.py`
  - `packages/evaluation-harness/src/evaluation_harness/reporting/models.py`
  - `packages/evaluation-harness/src/evaluation_harness/reporting/json.py`
  - `packages/evaluation-harness/src/evaluation_harness/reporting/markdown.py`
  - `packages/repo-cli/src/repo_cli/unified_experiment.py`
  - `packages/repo-cli/tests/test_unified_experiment_cli.py`
- **Read first:**
  - existing baseline artifacts under `data/.../eval/audit-ghostty-20260210-6mo-s4242-r3-v3/`
  - `packages/evaluation-harness/tests/test_end_to_end_run.py`

---

## 10) Risks and Mitigations

1. Wrong target policy optimized  
   - Mitigation: explicit primary policy + policy-parallel reporting.

2. Denominator masking  
   - Mitigation: mandatory denominator panel + promotion on observed-and-nonempty slice.

3. Overly rigid truth framework  
   - Mitigation: declarative core + plugin escape hatch.

4. Ownership signal degradation  
   - Mitigation: path unification + quality gates + telemetry.

5. LLM drift/hallucination  
   - Mitigation: candidate whitelist + structured output + replay mode.

6. Schema churn breaks downstream consumers  
   - Mitigation: short additive migration + contract tests.

---

## 11) Progress Log

| Date | Phase | Change | Evidence | Notes |
|---|---|---|---|---|
| 2026-02-11 | Planning | Initial RFC + implementation checklist created | `docs/plans/ghostty-routing-eval-integration-rfc-20260211.md` | baseline alignment complete |
| 2026-02-11 | Planning | Updated plan to generic truth-policy framework (declarative + plugin) | `docs/plans/ghostty-routing-eval-integration-rfc-20260211.md` | customizable multi-target direction added |
| 2026-02-11 | Planning | Locked decisions + per-item touch/read file maps added | `docs/plans/ghostty-routing-eval-integration-rfc-20260211.md` | implementation-ready checklist structure |
| 2026-02-11 | Phase 0 | Truth-window wiring + policy/result contracts + regression tests | `packages/evaluation-harness/src/evaluation_harness/{config.py,truth.py,truth_policy.py,truth_schema.py,runner.py}` | committed as `phase 0: truth window correctness and contracts` |
| 2026-02-11 | Phase 1 | Policy-keyed per-PR/report outputs, plugin loader, explain `--policy`, manifest truth block | `packages/evaluation-harness/src/evaluation_harness/{runner.py,manifest.py,cli/app.py,reporting/markdown.py}`, `packages/repo-cli/src/repo_cli/unified_experiment.py` | committed as `phase 1: policy-keyed truth and reporting surfaces` |
| 2026-02-11 | Phase 2 | CODEOWNERS contract unification, `union` + `hybrid_ranker`, audit gates + promotion + doctor readiness | `packages/repo-routing/src/repo_routing/{registry.py,router/baselines/union.py,router/hybrid_ranker.py,predictor/features/{ownership.py,similarity.py,repo_priors.py}}`, `packages/repo-cli/src/repo_cli/unified_experiment.py` | committed as `phase 2: ownership restoration, deterministic union/hybrid, and audit gates` |
| 2026-02-11 | Phase 3 | `llm_rerank` replay/live/off, replay cache + schema validation, per-PR LLM artifacts/provenance, report telemetry, reproducibility tests | `packages/repo-routing/src/repo_routing/router/{llm_rerank.py,llm_cache.py,llm_schema.py}`, `packages/evaluation-harness/src/evaluation_harness/{runner.py,reporting/markdown.py}` | committed as `phase 3: llm replay integration, provenance artifacts, and telemetry` |

---

## 12) Evidence Index (key files)

- Unified orchestration/locking:  
  `packages/repo-cli/src/repo_cli/unified_experiment.py`, `packages/repo-cli/README.md`

- Runner/truth/config mismatch locus:  
  `packages/evaluation-harness/src/evaluation_harness/{runner.py,truth.py,config.py}`

- Report/manifest contracts:  
  `packages/evaluation-harness/src/evaluation_harness/{manifest.py,reporting/models.py,reporting/markdown.py}`

- Router contracts/baselines/registry:  
  `packages/repo-routing/src/repo_routing/{router/base.py,router/baselines/*.py,registry.py}`

- Feature/pipeline/LLM insertion points:  
  `packages/repo-routing/src/repo_routing/{predictor/pipeline.py,predictor/feature_extractor_v1.py,examples/llm_router_example.py}`

- Repo profile + artifact storage:  
  `packages/repo-routing/src/repo_routing/repo_profile/{builder.py,storage.py}`

- Ownership feature path references:  
  `packages/repo-routing/src/repo_routing/predictor/features/ownership.py`, `packages/repo-routing/src/repo_routing/paths.py`

- Artifact fetcher:  
  `packages/repo-ingestion/src/gh_history_ingestion/repo_artifacts/fetcher.py`

- Ingestion/event fidelity checks:  
  `packages/repo-ingestion/src/gh_history_ingestion/{storage/schema.py,storage/upsert.py,events/normalizers/pull_request.py}`

- Truth diagnostics tests and repo-profile runner tests:  
  `packages/evaluation-harness/tests/{test_truth_diagnostics.py,test_runner_repo_profile.py}`

- Ghostty baseline run artifacts:  
  `data/github/ghostty-org/ghostty/eval/audit-ghostty-20260210-6mo-s4242-r3-v3/{cohort.json,experiment.json,experiment_manifest.json,manifest.json,report.json,per_pr.jsonl}`

- Verification bundle + notebook:  
  `.../verification/*`, `notebooks/experiment_audit_ghostty_org_ghostty_audit_ghostty_20260210_6mo_s4242_r3_v3.py`
