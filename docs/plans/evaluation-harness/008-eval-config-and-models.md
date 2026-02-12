# 008 - Define eval config + report schemas

- [ ] Done

## Goal
Make the evaluation reproducible by capturing config, sample selection, and results in typed schemas.

## Work
- Define Pydantic models for config, run metadata, and metric outputs.
- Ensure models capture:
  - repo, time window, sample size, seed
  - cutoff policy (default `created_at`; alternates `ready_for_review`, `created_at + delta`)
  - truth policy (requested reviewers window default 60 minutes; behavior truth = first review)
  - filtering policy (exclude bots + author)
  - candidate pool policy (default: last 180 days reviewers/commenters as-of cutoff)
  - router/baseline selection
  - evaluation `top_k` (default 5)
  - DB watermarks

## Files
Create:
- `packages/evaluation/src/evaluation_harness/config.py`
- `packages/evaluation/src/evaluation_harness/models.py`

## Acceptance Criteria
- Every `repo evaluation run` writes a `manifest.json` containing config + sample list + watermarks + pinned defaults actually used.
