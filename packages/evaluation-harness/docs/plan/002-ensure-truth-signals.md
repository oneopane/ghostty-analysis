# 002 - Ensure reviewer/commenter truth signals exist for the eval window

- [ ] Done

## Goal
Guarantee the offline DB contains the ground-truth signals needed for evaluation (requested reviewers, actual reviewers, and optionally commenters) for the sampled PRs.

## Work
Choose one path and document the recommended operational flow:
- Use full ingest for the repo and then incremental updates.
- Or extend the PR-window ingest (`pull-requests`) to also fetch reviews/comments/issue-events for PRs in the window.

## Files
Possible touch points:
- `packages/repo-ingestion/src/gh_history_ingestion/ingest/pull_requests.py`
- `packages/repo-ingestion/src/gh_history_ingestion/ingest/backfill.py`
- `packages/repo-ingestion/src/gh_history_ingestion/intervals/rebuild.py`
- `packages/repo-ingestion/README.md` (document which command to run to populate truth)

## Acceptance Criteria
- For a sampled PR, the DB can compute:
  - requested reviewers/teams shortly after open
  - review submitters
  - non-author commenters (optional)
- The eval harness can detect and report missing truth due to ingestion gaps.
