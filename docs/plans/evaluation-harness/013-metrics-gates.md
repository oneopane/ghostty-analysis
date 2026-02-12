# 013 - Implement gate correlation metrics

- [x] Done

## Goal
Measure directional correlation between missing policy fields and outcomes.

## Work
- Parse gate fields from PR body via inference parser.
- Compute merged rate for:
  - missing issue link
  - missing AI disclosure
  - missing provenance
- Record counts and caveats (sample size, missing data).

## Files
Create:
- `packages/evaluation/src/evaluation_harness/metrics/gates.py`

## Acceptance Criteria
- Output includes both raw counts and rates.
