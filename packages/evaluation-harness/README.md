# evaluation-harness

Minimal evaluation harness for routing and policy signals.

Planning checklist:

- `docs/plans/evaluation-harness/README.md`

Package docs:

- `packages/evaluation-harness/docs/runbook.md`
- `packages/evaluation-harness/docs/metrics.md`
- `packages/evaluation-harness/docs/baselines.md`

This package consumes per-repo history databases produced by `repo-ingestion` and
artifacts/heuristics from `repo-routing`.

Default per-repo DB location is:

`data/github/<owner>/<repo>/history.sqlite`

Use via the unified CLI:

`repo eval --help`
