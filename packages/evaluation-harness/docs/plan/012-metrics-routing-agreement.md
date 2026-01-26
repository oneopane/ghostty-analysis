# 012 - Implement routing agreement metrics

- [ ] Done

## Goal
Compute agreement between router suggestions and truth sets.

## Work
- Compute per-PR:
  - top-1 hit
  - top-3 hit
  - MRR (optional)
- Aggregate metrics separately for:
  - requested reviewers/teams (intent)
  - actual reviewers (behavior)

## Files
Create:
- `packages/evaluation-harness/src/evaluation_harness/metrics/__init__.py`
- `packages/evaluation-harness/src/evaluation_harness/metrics/routing_agreement.py`

## Acceptance Criteria
- Metrics computed for both user and team targets (reported separately).
