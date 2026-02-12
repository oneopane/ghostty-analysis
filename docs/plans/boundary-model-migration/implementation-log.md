# Implementation Log: Boundary Model Migration

This log is intended to be updated as implementation proceeds.

## Program Status

- Program: Boundary Model Migration
- Start date: 2026-02-11
- Owner: TBD
- Current phase: Implementation
- Current PR: PR-04 (In progress)

## PR Tracking Table

| PR | Title | Status | Owner | Branch/Change | Start | End | Notes |
|---|---|---|---|---|---|---|---|
| PR-01 | Boundary core and artifacts | In progress | oneopane | TBD | 2026-02-11 | - | boundary package + tests scaffolded |
| PR-02 | Hybrid inference v1 | Complete | oneopane | TBD | 2026-02-11 | 2026-02-11 | strategy registry + hybrid v1 + boundary CLI build scaffolded |
| PR-03 | Inputs/analysis/risk cutover | Complete | oneopane | TBD | 2026-02-11 | 2026-02-11 | boundary projection + input/analysis/risk/labels/receipt cutover |
| PR-04 | Predictor feature stack migration | In progress | oneopane | TBD | 2026-02-11 | - | boundary feature keys migrated across extractor/registry/policy/tests |
| PR-05 | Mixed-membership boundary migration | Planned | TBD | TBD | - | - | |
| PR-06 | Parser plugin framework + Python backend | Planned | TBD | TBD | - | - | |
| PR-07 | Zig + TS/JS parser backends + cleanup | Planned | TBD | TBD | - | - | |

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
- [ ] area references removed from runtime path

### M4: Predictor migration
- [x] boundary feature keys registered
- [x] task policy updated
- [x] feature extraction tests green

### M5: Mixed-membership migration
- [ ] boundary basis row builder complete
- [ ] NMF pipeline switched to boundary basis
- [ ] mixed-membership tests green

### M6: Parser framework + Python
- [ ] parser registry and contract merged
- [ ] Python backend integrated
- [ ] parser fallback behavior validated

### M7: Zig/TS/JS + cleanup
- [ ] Zig backend merged
- [ ] TS/JS backend merged
- [ ] terminology/docs cleanup complete

## Validation Ledger

### Determinism
- [ ] same config/input hash reproducibility verified
- [ ] no unstable ordering in outputs

### Cutoff safety
- [ ] leak tests for SQL sources
- [ ] parser sources constrained to pinned refs

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
| R4 | Terminology drift between docs and code | Medium | PR-07 cleanup checklist | Open |

## Decisions Referenced

See [`decision-log.md`](./decision-log.md).
