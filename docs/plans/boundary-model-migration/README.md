# Boundary Model Migration Plan (Index)

This directory contains the full implementation planning set for replacing `area` with a first-class **Boundary Model** in `packages/inference/src/repo_routing`.

## Documents

- [`overview.md`](./overview.md) — end-to-end architecture and phased rollout summary.
- [`decision-log.md`](./decision-log.md) — decisions, rationale, alternatives considered, open questions.
- [`implementation-log.md`](./implementation-log.md) — execution tracker template and status ledger.

## PR Plan Documents

- [`prs/PR-01-boundary-core-and-artifacts.md`](./prs/PR-01-boundary-core-and-artifacts.md)
- [`prs/PR-02-hybrid-inference-v1.md`](./prs/PR-02-hybrid-inference-v1.md)
- [`prs/PR-03-inputs-analysis-risk-cutover.md`](./prs/PR-03-inputs-analysis-risk-cutover.md)
- [`prs/PR-04-predictor-feature-stack-migration.md`](./prs/PR-04-predictor-feature-stack-migration.md)
- [`prs/PR-05-mixed-membership-boundary-migration.md`](./prs/PR-05-mixed-membership-boundary-migration.md)
- [`prs/PR-06-parser-plugin-framework-and-python-backend.md`](./prs/PR-06-parser-plugin-framework-and-python-backend.md)
- [`prs/PR-07-zig-ts-js-backends-and-cleanup.md`](./prs/PR-07-zig-ts-js-backends-and-cleanup.md)

## Scope

- Design + implementation planning only.
- No code changes included in this planning set.
- Explicitly targets deterministic, cutoff-safe behavior.
