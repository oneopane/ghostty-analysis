# 016 - Implement run output layout + manifests

- [ ] Done

## Goal
Standardize output paths and ensure every run is self-describing.

## Work
- Compute run IDs (timestamp + config hash).
- Write `manifest.json` with:
  - config
  - sampled PR list
  - DB watermark
  - router versions

## Files
Create:
- `packages/evaluation-harness/src/evaluation_harness/run_id.py`
- `packages/evaluation-harness/src/evaluation_harness/manifest.py`
- `packages/evaluation-harness/src/evaluation_harness/store/__init__.py`
- `packages/evaluation-harness/src/evaluation_harness/store/filesystem.py`

## Acceptance Criteria
- Outputs go to: `data/github/<owner>/<repo>/eval/<run_id>/...`.
