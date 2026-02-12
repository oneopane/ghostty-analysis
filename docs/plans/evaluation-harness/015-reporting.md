# 015 - Implement report aggregation + formatting

- [x] Done

## Goal
Emit a human one-page report and machine-readable output for reproducibility.

## Work
- Write `report.md` with:
  - key metrics
  - sample details
  - caveats (gaps, missing signals)
- Write `report.json` for programmatic consumption.
- Write `per_pr.jsonl` for per-PR debugging and examples.

## Files
Create:
- `packages/evaluation/src/evaluation_harness/reporting/__init__.py`
- `packages/evaluation/src/evaluation_harness/reporting/markdown.py`
- `packages/evaluation/src/evaluation_harness/reporting/json.py`
- `packages/evaluation/src/evaluation_harness/reporting/formatters.py`

## Acceptance Criteria
- Report is stable (ordering deterministic) and includes watermark/version info.
