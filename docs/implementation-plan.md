# Implementation Plan: Repository-Agnostic History Dataset Pipeline

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

## Pipeline Phases

### 1) Schema Initialization
- Create tables and indexes.
- Treat `events` as append-only canonical history.
- Use GitHub database IDs as primary keys where available.

### 2) Full Backfill (One-Time)
- **Commits**: paginate newest to oldest; store SHAs and commit metadata.
- **Pull requests**: list all PRs; for each PR fetch reviews, review comments, issue comments, and issue events.
- **Refs/releases**: fetch branches, tags, releases for markers.
- Normalize every payload into:
  - Identity tables
  - Object tables (issues, PRs, reviews, comments)
  - Event log rows

### 3) Derive Intervals
- Replay events in deterministic order (occurred_at, event_id).
- Materialize interval tables (labels, assignees, milestone, draft, head SHA, content).

### 4) Incremental Updates
- Maintain watermarks per resource type (PRs by updated_at, comments by since, commits by since).
- Fetch deltas using GitHub pagination and conditional requests.
- Upsert into identity/object tables; append events.
- Rebuild intervals for updated PRs/issues only.

### 5) Idempotency and Dedupe
- Use GitHub IDs as stable primary keys.
- Upsert on conflict for object tables.
- Event log is append-only; de-duplicate by event_id or a stable composite key when needed.

### 6) Rate Limits and Reliability
- Respect GitHub rate limits and secondary rate limits.
- Implement retry with backoff on 403 or 429.
- Use conditional requests (ETag or If-Modified-Since) to reduce cost.

### 7) Verification and QA
- Sample PRs: compare reconstructed timelines with GitHub UI.
- Validate interval tables by spot checks against raw event sequences.
- Track gaps (missing pages, timestamp discontinuities).

## Output Guarantees
- Reproducible state at any time t using event replay + intervals.
- No leakage in evaluation: features must only use events <= t.
- Compatibility across repositories with different policies and templates.

## Operational Considerations
- Store access tokens securely; avoid logging secrets.
- Support multiple repos by namespacing with repo_id.
- Optional redaction for text fields if policy requires.
