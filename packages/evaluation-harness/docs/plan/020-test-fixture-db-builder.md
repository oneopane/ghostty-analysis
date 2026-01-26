# 020 - Add synthetic DB fixture builder

- [ ] Done

## Goal
Create a minimal SQLite DB in tests (no large committed DB files) to validate end-to-end logic.

## Work
- Build a temporary `history.sqlite` with minimal tables/rows needed for evaluation.
- Include at least:
  - one PR
  - one review request
  - one review submission
  - one comment
  - (optional) PR files

## Files
Create:
- `packages/evaluation-harness/tests/fixtures/build_min_db.py`

## Acceptance Criteria
- Tests can run without network.
