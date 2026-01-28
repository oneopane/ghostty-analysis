# 009 - Implement cutoff policy

- [ ] Done

## Goal
Define how to choose the evaluation cutoff timestamp per PR (avoid draft leakage and align with triage reality).

## Work
- Support cutoffs:
  - `created_at`
  - `ready_for_review` (when available)
  - `created_at + delta`
- Default cutoff: `created_at`.
- Ensure the chosen cutoff is recorded per PR.

## Files
Create:
- `packages/evaluation-harness/src/evaluation_harness/cutoff.py`

## Acceptance Criteria
- Cutoff logic is unit-tested and deterministic.
