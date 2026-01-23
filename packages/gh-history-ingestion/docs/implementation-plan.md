# Implementation Plan: Repository-Agnostic History Dataset Pipeline

## Progress (as of 2026-01-23)
- [x] Schema initialization (SQLite/SQLAlchemy) with all identity, object, event, interval tables.
- [x] REST client with pagination, retry/backoff, and rate limiting.
- [x] Full one-shot backfill for repo metadata, issues, PRs, reviews, review comments, issue comments, issue events.
- [x] Event normalization for core issue/PR/review/comment workflows.
- [x] Interval rebuild for issue state/labels/content/assignees/milestones, PR draft/head/review requests, comment/review content.
- [ ] Commits backfill (commit list + metadata, SHAs only).
- [ ] Refs/releases backfill (branches, tags, releases as markers).
- [ ] Incremental updates + watermarks (explicitly out of scope for one-shot only runs).
- [ ] Conditional requests (ETag / If-Modified-Since).
- [ ] QA reporting / gap detection for missing pages or discontinuities.
- [x] Complete event payload coverage (map all GitHub issue/PR timeline events to canonical events).

### Implementation Notes
- Backfill currently covers repo metadata, issues, PRs, reviews, review comments, issue comments, and issue events; commits/refs/releases are not yet ingested.
- Events are normalized for the core subset and include a generic fallback mapping for any unknown issue/PR events so no payloads are dropped.
- Interval rebuild is deterministic and idempotent for the supported event set.

## Goals
- Build a repeatable pipeline that can construct the dataset for any GitHub repository.
- Support full historical backfill and ongoing incremental updates.
- Maintain a canonical event log with derived intervals for as-of queries.
- Preserve commit SHAs only (no git blobs or trees).

## Inputs and Sources
Use GitHub REST API endpoints for:
- Repository metadata, branches, tags, releases
- Pull requests, reviews, review comments
- Issues, issue comments, issue events/timeline
- Commits (metadata and SHAs only)

## Project Layout
Workspace package location:
- `packages/gh-history-ingestion/`

Core modules (planned):
- `src/gh_history_ingestion/github/` (API client, pagination, rate limits)
- `src/gh_history_ingestion/ingest/` (backfill + incremental)
- `src/gh_history_ingestion/storage/` (DB engine + schema)
- `src/gh_history_ingestion/events/` (event normalization)
- `src/gh_history_ingestion/intervals/` (interval rebuild)
- `src/gh_history_ingestion/cli/` (Typer CLI entrypoints)

## Pipeline Phases

### 1) Schema Initialization
- Create tables and indexes.
- Treat `events` as append-only canonical history.
- Use GitHub database IDs as primary keys where available.
Completion criteria:
- All tables and indexes created successfully.
- A minimal insert into each table succeeds without errors.
- `events` supports append-only inserts with monotonic event_id ordering.

### 2) Full Backfill (One-Time)
- **Commits**: paginate newest to oldest; store SHAs and commit metadata.
- **Pull requests**: list all PRs; for each PR fetch reviews, review comments, issue comments, and issue events.
- **Refs/releases**: fetch branches, tags, releases for markers.
- Normalize every payload into:
  - Identity tables
  - Object tables (issues, PRs, reviews, comments)
  - Event log rows
Completion criteria:
- All PRs/Issues in the target repo are present locally.
- Event counts match GitHub totals within expected API limitations.
- Backfill can be re-run without creating duplicate rows.

### 3) Derive Intervals
- Replay events in deterministic order (occurred_at, event_id).
- Materialize interval tables (labels, assignees, milestone, draft, head SHA, content).
Completion criteria:
- Interval tables are populated for all PRs/issues in scope.
- As-of queries return consistent results for sampled timestamps.
- Rebuilding intervals is idempotent and completes within acceptable time.

### 4) Incremental Updates
- Maintain watermarks per resource type (PRs by updated_at, comments by since, commits by since).
- Fetch deltas using GitHub pagination and conditional requests.
- Upsert into identity/object tables; append events.
- Rebuild intervals for updated PRs/issues only.
Completion criteria:
- Incremental run fetches only new or changed records.
- Watermarks advance reliably without gaps.
- Updated PRs/issues reflect new events and interval changes.

### 5) Idempotency and Dedupe
- Use GitHub IDs as stable primary keys.
- Upsert on conflict for object tables.
- Event log is append-only; de-duplicate by event_id or a stable composite key when needed.
Completion criteria:
- Re-running the same fetch produces zero net-new rows.
- Duplicate API payloads do not create duplicate events.
- Integrity constraints hold across all tables.

### 6) Rate Limits and Reliability
- Respect GitHub rate limits and secondary rate limits.
- Implement retry with backoff on 403 or 429.
- Use conditional requests (ETag or If-Modified-Since) to reduce cost.
Completion criteria:
- Runs complete without triggering secondary rate limit blocks.
- Retries are bounded and logged, with successful recovery.
- Conditional requests yield 304 responses when appropriate.

### 7) Verification and QA
- Sample PRs: compare reconstructed timelines with GitHub UI.
- Validate interval tables by spot checks against raw event sequences.
- Track gaps (missing pages, timestamp discontinuities).
Completion criteria:
- Sampled PR timelines match GitHub UI ordering and content.
- Any gaps are detected and recorded for remediation.
- QA reports are produced for each backfill run.

## Output Guarantees
- Reproducible state at any time t using event replay + intervals.
- No leakage in evaluation: features must only use events <= t.
- Compatibility across repositories with different policies and templates.

## Operational Considerations
- Prefer GitHub CLI auth when available; fall back to `GITHUB_TOKEN`.
- Store access tokens securely; avoid logging secrets.
- Support multiple repos by namespacing with repo_id.
- Optional redaction for text fields if policy requires.
