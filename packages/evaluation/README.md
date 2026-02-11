# evaluation

## Start here

For the canonical CLI-first lifecycle that includes evaluation outputs and quality checks:

- `../../docs/examples/e2e-unified-cli.md`

Offline evaluation harness for routing and policy signals.

Planning checklist:

- `docs/plans/evaluation-harness/README.md`

Package docs:

- `packages/evaluation/docs/runbook.md`
- `packages/evaluation/docs/metrics.md`
- `packages/evaluation/docs/baselines.md`

This package consumes per-repo history databases produced by `ingestion` and
routing artifacts/heuristics from `inference`.

Default DB path:

`data/github/<owner>/<repo>/history.sqlite`

Unified CLI surface:

`repo evaluation --help`
