# 026 - Add evaluation runbook + metric definitions

- [x] Done

## Goal
Make it easy to run evaluation and interpret results.

## Work
- Add a runbook with common commands and output locations.
- Define each metric precisely (what counts as a hit, how bots are filtered, etc.).

## Files
Create:
- `packages/evaluation-harness/docs/runbook.md`
- `packages/evaluation-harness/docs/metrics.md`

## Acceptance Criteria
- Someone can run `repo eval run` and understand the report without reading source.
