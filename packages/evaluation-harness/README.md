# evaluation-harness

Minimal evaluation harness for routing and policy signals.

Implementation checklist: `packages/evaluation-harness/docs/plan/README.md`

This package consumes per-repo history databases produced by `repo-ingestion` and
artifacts/heuristics from `repo-routing`.

Default per-repo DB location is:

`data/github/<owner>/<repo>/history.sqlite`

Use via the unified CLI:

`repo eval --help`
