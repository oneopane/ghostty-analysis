# experimentation

## Start here

For the full user-facing golden path, including cohort/spec/run/diff/quality checks:

- `../../docs/examples/e2e-unified-cli.md`

Experiment workflow helpers and orchestration logic.

This package contains:

- cohort/spec lifecycle commands (`cohort`, `experiment`, `profile`, `doctor`)
- run manifests, quality gates, and promotion checks
- reusable marimo UI components for ingestion/export/eval loops

The unified `repo` CLI in `packages/cli` mounts these commands.
