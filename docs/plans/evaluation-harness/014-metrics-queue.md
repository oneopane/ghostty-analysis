# 014 - Implement queue metrics (TTFR/TTFC)

- [x] Done

## Goal
Compute simple queue metrics to compare high-risk vs low-risk routing buckets.

## Work
- TTFR: first non-author review submission time minus cutoff start.
- Optional TTFC: first non-author comment time minus cutoff start.
- Split by risk/confidence buckets.

## Files
Create:
- `packages/evaluation/src/evaluation_harness/metrics/queue.py`

## Acceptance Criteria
- If data is missing, metric is skipped with an explicit note.
