# 008 - Define eval config + report schemas

- [ ] Done

## Goal
Make the evaluation harness reproducible by capturing config, sample selection, and results in typed schemas.

## Work
- Define Pydantic models for config, run metadata, and metric outputs.
- Ensure models capture:
  - repo, time window, sample size, seed
  - cutoff policy
  - router/baseline selection
  - DB watermarks

## Files
Create:
- `packages/evaluation-harness/src/evaluation_harness/config.py`
- `packages/evaluation-harness/src/evaluation_harness/models.py`

## Acceptance Criteria
- Every `repo eval run` writes a `manifest.json` containing the config + sample list + watermarks.
