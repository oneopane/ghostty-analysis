# 010 - Implement deterministic sampling

- [ ] Done

## Goal
Select PRs for evaluation deterministically (so metrics are reproducible).

## Work
- Implement sampling strategies:
  - last N PRs by created time
  - random PRs within a time window with a seed
- Persist sampled PR identifiers (numbers/ids) in the run manifest.

## Files
Create:
- `packages/evaluation-harness/src/evaluation_harness/sampling/__init__.py`
- `packages/evaluation-harness/src/evaluation_harness/sampling/select.py`

## Acceptance Criteria
- Given the same inputs (db + window + seed), sample list is identical.
