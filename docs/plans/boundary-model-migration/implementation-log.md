# Implementation Log: Boundary Model Migration

This log is intended to be updated as implementation proceeds.

## Program Status

- Program: Boundary Model Migration
- Start date: 2026-02-11
- Owner: oneopane
- Current phase: Completed
- Current PR: PR-07 (Complete)

## PR Tracking Table

| PR | Title | Status | Owner | Branch/Change | Start | End | Notes |
|---|---|---|---|---|---|---|---|
| PR-01 | Boundary core and artifacts | Complete | oneopane | TBD | 2026-02-11 | 2026-02-11 | boundary package + tests scaffolded |
| PR-02 | Hybrid inference v1 | Complete | oneopane | TBD | 2026-02-11 | 2026-02-11 | strategy registry + hybrid v1 + boundary CLI build scaffolded |
| PR-03 | Inputs/analysis/risk cutover | Complete | oneopane | TBD | 2026-02-11 | 2026-02-11 | boundary projection + input/analysis/risk/labels/receipt cutover |
| PR-04 | Predictor feature stack migration | Complete | oneopane | TBD | 2026-02-11 | 2026-02-11 | boundary feature keys migrated across extractor/registry/policy/tests |
| PR-05 | Mixed-membership boundary migration | Complete | oneopane | TBD | 2026-02-11 | 2026-02-11 | boundary-basis mixed-membership APIs + artifacts + notebook migration |
| PR-06 | Parser plugin framework + Python backend | Complete | oneopane | TBD | 2026-02-11 | 2026-02-11 | parser registry + python backend + hybrid parser channel + fallback tests |
| PR-07 | Zig + TS/JS parser backends + cleanup | Complete | oneopane | TBD | 2026-02-11 | 2026-02-11 | zig+ts/js parser backends + final boundary terminology cleanup |

## Milestone Checkpoints

### M1: Boundary Core + Artifact IO
- [x] schemas committed
- [x] deterministic hash tests passing
- [x] artifact read/write tests passing

### M2: Hybrid inference v1
- [x] cutoff-safe inference tests passing
- [x] deterministic tie-break tests passing
- [x] CLI build command available

### M3: Runtime cutover
- [x] input bundle boundary fields active
- [x] analysis/risk boundary logic active
- [x] area references removed from runtime path

### M4: Predictor migration
- [x] boundary feature keys registered
- [x] task policy updated
- [x] feature extraction tests green

### M5: Mixed-membership migration
- [x] boundary basis row builder complete
- [x] NMF pipeline switched to boundary basis
- [x] mixed-membership tests green

### M6: Parser framework + Python
- [x] parser registry and contract merged
- [x] Python backend integrated
- [x] parser fallback behavior validated

### M7: Zig/TS/JS + cleanup
- [x] Zig backend merged
- [x] TS/JS backend merged
- [x] terminology/docs cleanup complete

## Validation Ledger

### Determinism
- [x] same config/input hash reproducibility verified
- [x] no unstable ordering in outputs

### Cutoff safety
- [x] leak tests for SQL sources
- [x] parser sources constrained to pinned refs

### Routing quality
- [ ] baseline comparison run complete
- [ ] primary metrics reviewed (MRR/Hit@k)

### Stability / Interpretability
- [ ] boundary count drift checks across adjacent cutoffs
- [ ] sampled PR footprint interpretability review

## Risk Log

| ID | Risk | Severity | Mitigation | Status |
|---|---|---|---|---|
| R1 | Low-data repos produce unstable partitions | Medium | fallback partition + confidence metadata | Open |
| R2 | Parser backend failures degrade outputs | Medium | optional parser channels + deterministic fallback | Open |
| R3 | Feature key churn breaks task policy expectations | High | dedicated PR-04 + policy tests | Open |
| R4 | Terminology drift between docs and code | Medium | PR-07 cleanup checklist | Closed |

## Decisions Referenced

See [`decision-log.md`](./decision-log.md).
