# GitHub Repository History Dataset (Event-Sourced)

## Purpose
Provide a repository-agnostic, metadata-only dataset that captures the full history of a GitHub repository in a form suitable for temporal replay and offline evaluation of PR triage workflows. The dataset is designed to support point-in-time reconstruction (state at time t) and predictive labels based on events after time t.

## Scope
- Works for any GitHub repository.
- Stores metadata and relationships only.
- Commit SHAs are retained as references; no git blobs or trees are stored.
- Supports both PRs and issues; PRs are a specialized case of issues.

## Core Formalism
The dataset is event-sourced:
- **Entities** are stable objects (repo, user, PR, issue, label).
- **Events** are immutable changes in time (opened, labeled, commented).
- **Intervals** are derived views that make as-of state queries efficient.

State at time t is defined by replaying events ordered by (occurred_at, event_id), then selecting interval rows active at t.

## Schema Overview

### Identity Tables (Stable IDs)
- `repos`: repository identity and metadata.
- `users`: user identity, login, type.
- `teams`: team identity (optional, for review requests).
- `labels`: label identity within a repo.
- `milestones`: milestone identity within a repo.

### Core Objects
- `issues`: issue identity and creation metadata (includes PRs).
- `pull_requests`: PR-specific fields (base/head refs, merge info).
- `reviews`: PR review metadata.
- `comments`: issue, review, and diff comments (unified).

### Event Log (Canonical Timeline)
- `events`: append-only history of everything that changes.
  - Required fields: repo_id, occurred_at, actor_id, subject_type, subject_id, event_type.
  - Optional fields: object_type, object_id, commit_sha, payload_json.

### Interval Tables (Derived)
Intervals provide efficient as-of queries without full replay:
- `issue_state_intervals` (open/closed).
- `issue_content_intervals` (title/body edits).
- `issue_label_intervals`.
- `issue_assignee_intervals`.
- `issue_milestone_intervals`.
- `pull_request_draft_intervals`.
- `pull_request_head_intervals`.
- `pull_request_review_request_intervals`.
- `comment_content_intervals`.
- `review_content_intervals`.

### Optional Raw Snapshots
- `object_snapshots`: raw JSON snapshots keyed by event_id for exact historical fidelity.

## Event Vocabulary (Examples)
Event types are an open set. Examples include:
- `issue.opened`, `issue.closed`, `issue.reopened`
- `issue.label.add`, `issue.label.remove`
- `issue.assignee.add`, `issue.assignee.remove`
- `issue.milestone.set`, `issue.milestone.clear`
- `pull_request.merged`, `pull_request.ready_for_review`, `pull_request.synchronize`
- `comment.created`, `comment.edited`, `comment.deleted`
- `review.submitted`, `review.edited`, `review.dismissed`

## Temporal Reconstruction
To reconstruct state at time t:
1. Map time t to the latest event_id with occurred_at <= t.
2. Query interval tables where start_event_id <= cutoff_event_id and (end_event_id is null or cutoff_event_id < end_event_id).
3. Use identity tables for stable metadata (repo, user, label info).

## Data Retention and Leakage Rules
- Store only metadata needed for replay, labeling, and feature extraction.
- Commit SHAs only; no git blobs or trees.
- Avoid using any post-t0 events when constructing evaluation snapshots.
- Optional redaction or hashing of text fields if policy requires.

## Query Patterns (Typical)
- PR timeline: all events for a PR ordered by time.
- PR state at time t: interval tables filtered by cutoff.
- Label history: label intervals by PR/issue.
- Review readiness features: counts of review requests and submitted reviews up to t.

## Limitations
- Edit histories may be incomplete without raw snapshots.
- Force-push events may not expose full commit graph; head SHAs capture sufficient triage metadata.
- API rate limits require careful backfill and incremental update design.
