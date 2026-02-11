# 024 - Add leakage + bot filtering guardrail tests

- [x] Done

## Goal
Prevent accidental leakage and noisy truths.

## Work
- Test bot filtering logic.
- Test that router cannot use data after cutoff (at least via invariants/watermarks).

## Files
Create:
- `packages/evaluation-harness/tests/test_leakage_guards.py`
- `packages/evaluation-harness/tests/test_bot_filtering.py`

## Acceptance Criteria
- Guardrails fail loudly if invariants are violated.
