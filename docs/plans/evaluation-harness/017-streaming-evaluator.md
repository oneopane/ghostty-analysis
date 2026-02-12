# 017 - Implement streaming evaluator (leakage-safe)

- [x] Done

## Goal
Evaluate PRs in time order, ensuring router state never sees future events.

## Work
- Iterate sampled PRs ordered by cutoff time.
- For each PR:
  - build `PRContext` as-of cutoff
  - call router
  - compute truth + per-PR metrics
  - append to `per_pr.jsonl`
- Aggregate metrics at end and write reports.

## Files
Create:
- `packages/evaluation/src/evaluation_harness/runner.py`

## Acceptance Criteria
- Evaluation runs are deterministic.
- Leak checks exist (e.g. cutoff <= watermark used by router).
