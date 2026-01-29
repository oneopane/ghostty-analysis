# 018 - Add repo eval commands (run/show/explain/list)

- [x] Done

## Goal
Provide minimal CLI UX to run evaluation and inspect results.

## Work
- `repo eval run`: perform an evaluation and write outputs.
- `repo eval show`: pretty-print a report.
- `repo eval explain`: print route + evidence + truths for one PR.
- `repo eval list`: list run directories.

Defaults (v0):
- cutoff: `created_at`
- requested reviewer window: 60 minutes
- `top_k=5`

## Files
Touch:
- `packages/evaluation-harness/src/evaluation_harness/cli/app.py`

Create:
- `packages/evaluation-harness/src/evaluation_harness/cli/__init__.py`
- `packages/evaluation-harness/src/evaluation_harness/cli/run.py`
- `packages/evaluation-harness/src/evaluation_harness/cli/show.py`
- `packages/evaluation-harness/src/evaluation_harness/cli/explain.py`
- `packages/evaluation-harness/src/evaluation_harness/cli/list_runs.py`

## Acceptance Criteria
- CLI never calls GitHub APIs.
- `repo eval run` exits non-zero on missing DB.
