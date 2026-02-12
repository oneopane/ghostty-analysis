# Overview: Boundary Model Migration (Area → Boundary)

## 1) Objective

Replace the current path-label `area` concept with a first-class **Boundary Model** that:

1. cleanly separates definition, inference, and consumption,
2. supports multiple granularities (`repo`, `dir`, `file`, `symbol`, `function`),
3. supports hard and mixed membership,
4. supports pluggable language-aware parsing signals,
5. remains deterministic and cutoff-safe for evaluation and experiments.

This plan assumes direct replacement (no backward-compatibility shim layer required).

---

## 2) High-Level Architecture

### 2.1 Boundary Definition
Canonical, versioned model types:
- `BoundaryUnit`
- `BoundaryDef`
- `Membership`
- `BoundaryModel`

Membership modes:
- **hard** (partition)
- **overlap**
- **mixed** (weights)

### 2.2 Boundary Inference
Pluggable strategy interface:
- strategy IDs + versions
- deterministic tie-breakers + canonical serialization
- signal channels:
  - path-derived signals
  - co-change graph signals
  - parser structural signals (imports, refs, symbol/function graph)

Default v1 strategy:
- `hybrid_path_cochange.v1` (no parser required)

### 2.3 Boundary Consumption
Boundary footprint is consumed by:
- input builder (`PRInputBundle` replacement fields)
- analysis/risk/scoring
- predictor feature stack
- mixed-membership modeling
- route evidence/receipts

---

## 3) Rollout Strategy

The migration is split into 7 PRs to reduce risk and simplify review:

1. **PR-01** boundary core schemas + artifacts
2. **PR-02** hybrid inference v1 (path + co-change)
3. **PR-03** cutover inputs + analysis + risk
4. **PR-04** predictor feature migration
5. **PR-05** mixed-membership migration
6. **PR-06** parser plugin framework + Python backend
7. **PR-07** Zig + TS/JS parser backends + terminology cleanup

Each PR has a dedicated detailed plan in `prs/`.

---

## 4) Determinism / Cutoff-Safety Guarantees

### Determinism requirements
- stable sorting and tie-breakers for all map/set/list outputs,
- canonical JSON serialization with sorted keys,
- fixed rounding policy for float outputs before hashing,
- explicit seed for stochastic algorithms,
- strategy/parser versions included in hashes.

### Cutoff-safety requirements
- as-of bounded SQL only (`<= cutoff`),
- no post-cutoff events,
- parser signals derived from pinned snapshot refs as-of cutoff/base,
- no network during inference (offline deterministic artifacts).

---

## 5) Artifact Plan (Target)

Default location:
- `data/github/<owner>/<repo>/artifacts/routing/boundary_model/<strategy_id>/<cutoff_key>/`

Core outputs:
- `boundary_model.json`
- `memberships.parquet`
- `signals.parquet` (optional by strategy)
- `manifest.json`

Required metadata:
- `schema_version`, `strategy_id`, `strategy_version`
- `repo`, `cutoff_utc`, DB watermark metadata
- parser bundle metadata (if used)
- canonical model hash

---

## 6) Validation Plan Summary

### Immediately possible (no new source snapshot requirements)
- deterministic reproducibility tests,
- cutoff leak tests,
- non-regression and uplift checks on routing metrics,
- stability checks across nearby cutoffs.

### Requires new inputs (pinned source snapshots + parser backends)
- parser coverage and diagnostics,
- symbol/function boundary quality checks,
- parser-signal uplift analysis vs non-parser baseline.

---

## 7) Risks and Mitigations

- **Risk:** low-signal repos produce noisy boundaries.  
  **Mitigation:** deterministic fallback partition + confidence metadata.

- **Risk:** parser unavailability/parse failures.  
  **Mitigation:** optional parser channels; always produce file-level boundary model.

- **Risk:** broad feature/key churn impacts task policies.  
  **Mitigation:** one dedicated PR for feature registry/policy migration + focused tests.

- **Risk:** docs/terminology drift after migration.  
  **Mitigation:** dedicated final cleanup PR with checklist-driven rename pass.

---

## 8) Completion Definition

Migration is complete when:
- no active routing path depends on `area_overrides.json` or `area_for_path`,
- PR input, scoring, and feature extraction are boundary-native,
- mixed-membership uses boundary basis,
- parser framework is integrated with at least one production backend (Python),
- docs and tests reflect boundary terminology and deterministic contracts.
