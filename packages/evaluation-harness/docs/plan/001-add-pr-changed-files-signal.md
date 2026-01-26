# 001 - Add PR changed files signal to history DB

- [ ] Done

## Goal
Persist per-PR changed file paths in the canonical per-repo SQLite database so routing and baselines can be evaluated offline.

## Work
- Add a raw `pull_request_files` table to the history DB (queryable, not JSON blobs).
- Ingest PR file lists via GitHub REST (`/pulls/{number}/files`) during backfill and incremental updates.

## Files
Touch:
- `packages/repo-ingestion/src/gh_history_ingestion/storage/schema.py`
- `packages/repo-ingestion/src/gh_history_ingestion/storage/upsert.py`
- `packages/repo-ingestion/src/gh_history_ingestion/ingest/backfill.py`
- `packages/repo-ingestion/src/gh_history_ingestion/ingest/incremental.py`

Create (if needed):
- `packages/repo-ingestion/src/gh_history_ingestion/ingest/pull_request_files.py`

## Acceptance Criteria
- For a PR with multiple commits, file paths are stored keyed by PR + head SHA.
- Re-running ingestion does not duplicate rows.
- Querying changed files for a PR head SHA is efficient (indexes exist).
