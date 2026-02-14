# Schemas

This repo uses SQLite as its primary normalized store (`history.sqlite`) and a secondary cross-run index DB (`examples_index.sqlite`).

## Primary DB: `history.sqlite` {#primary-db-history-sqlite}

Schema source:

- ORM models: `packages/ingestion/src/gh_history_ingestion/storage/schema.py`
- Created via: `packages/ingestion/src/gh_history_ingestion/storage/db.py` (`Base.metadata.create_all`)
- No migration framework found (no Alembic); schema evolves via ORM + recreate/alter patterns.

### Table Dictionary

Notes:

- Types are SQLAlchemy column types from `schema.py`.
- Keys list primary key columns.

#### repos {#table-repos}

Grain: 1 row per GitHub repo.

| Column | Type |
|---|---|
| id | BigInteger (PK) |
| owner_id | BigInteger |
| owner_login | String |
| name | String |
| full_name | String (unique) |
| is_private | Boolean |
| description | Text |
| default_branch | String |
| created_at | DateTime(tz) |
| updated_at | DateTime(tz) |
| pushed_at | DateTime(tz) |
| archived | Boolean |
| disabled | Boolean |

#### users {#table-users}

Grain: 1 row per GitHub user.

| Column | Type |
|---|---|
| id | BigInteger (PK) |
| login | String |
| type | String |
| site_admin | Boolean |
| avatar_url | String |

#### teams {#table-teams}

Grain: 1 row per GitHub team.

| Column | Type |
|---|---|
| id | BigInteger (PK) |
| slug | String |
| name | String |

#### labels {#table-labels}

Grain: 1 row per GitHub label id.

| Column | Type |
|---|---|
| id | BigInteger (PK) |
| repo_id | BigInteger (FK -> repos.id) |
| name | String |
| color | String |
| description | Text |
| is_default | Boolean |

#### milestones {#table-milestones}

Grain: 1 row per GitHub milestone id.

| Column | Type |
|---|---|
| id | BigInteger (PK) |
| repo_id | BigInteger (FK -> repos.id) |
| number | Integer |
| title | String |
| state | String |
| description | Text |
| due_on | DateTime(tz) |
| closed_at | DateTime(tz) |
| created_at | DateTime(tz) |
| updated_at | DateTime(tz) |

#### issues {#table-issues}

Grain: 1 row per GitHub issue id; unique (repo_id, number).

| Column | Type |
|---|---|
| id | BigInteger (PK) |
| repo_id | BigInteger (FK -> repos.id) |
| number | Integer (unique per repo) |
| user_id | BigInteger (FK -> users.id) |
| title | String |
| body | Text |
| state | String |
| created_at | DateTime(tz) |
| updated_at | DateTime(tz) |
| closed_at | DateTime(tz) |
| is_pull_request | Boolean |
| locked | Boolean |

#### pull_requests {#table-pull_requests}

Grain: 1 row per GitHub PR id; unique (repo_id, number).

| Column | Type |
|---|---|
| id | BigInteger (PK) |
| repo_id | BigInteger (FK -> repos.id) |
| number | Integer (unique per repo) |
| issue_id | BigInteger (FK -> issues.id) |
| user_id | BigInteger (FK -> users.id) |
| title | String |
| body | Text |
| state | String |
| draft | Boolean |
| merged | Boolean |
| merge_commit_sha | String |
| head_sha | String |
| head_ref | String |
| base_sha | String |
| base_ref | String |
| created_at | DateTime(tz) |
| updated_at | DateTime(tz) |
| closed_at | DateTime(tz) |
| merged_at | DateTime(tz) |

#### pull_request_files {#table-pull_request_files}

Grain: per (repo_id, pull_request_id, head_sha, path).

Primary key: (repo_id, pull_request_id, head_sha, path).

| Column | Type |
|---|---|
| repo_id | BigInteger (PK, FK -> repos.id) |
| pull_request_id | BigInteger (PK, FK -> pull_requests.id) |
| head_sha | String (PK) |
| path | String (PK) |
| status | String |
| additions | Integer |
| deletions | Integer |
| changes | Integer |

#### reviews {#table-reviews}

Grain: 1 row per GitHub review id.

| Column | Type |
|---|---|
| id | BigInteger (PK) |
| repo_id | BigInteger (FK -> repos.id) |
| pull_request_id | BigInteger (FK -> pull_requests.id) |
| user_id | BigInteger (FK -> users.id) |
| state | String |
| body | Text |
| submitted_at | DateTime(tz) |
| commit_id | String |

#### comments {#table-comments}

Grain: 1 row per GitHub comment id (issue/PR/review comment).

| Column | Type |
|---|---|
| id | BigInteger (PK) |
| repo_id | BigInteger (FK -> repos.id) |
| issue_id | BigInteger (FK -> issues.id) |
| pull_request_id | BigInteger (FK -> pull_requests.id) |
| review_id | BigInteger (FK -> reviews.id) |
| user_id | BigInteger (FK -> users.id) |
| body | Text |
| created_at | DateTime(tz) |
| updated_at | DateTime(tz) |
| path | String |
| position | Integer |
| commit_id | String |
| in_reply_to_id | BigInteger |
| comment_type | String |

#### commits {#table-commits}

Grain: per (repo_id, sha).

Primary key: (repo_id, sha).

| Column | Type |
|---|---|
| repo_id | BigInteger (PK, FK -> repos.id) |
| sha | String (PK) |
| author_id | BigInteger (FK -> users.id) |
| committer_id | BigInteger (FK -> users.id) |
| author_name | String |
| author_email | String |
| committer_name | String |
| committer_email | String |
| message | Text |
| authored_at | DateTime(tz) |
| committed_at | DateTime(tz) |

#### refs {#table-refs}

Grain: per (repo_id, ref_type, name).

| Column | Type |
|---|---|
| id | Integer (PK) |
| repo_id | BigInteger (FK -> repos.id) |
| ref_type | String |
| name | String |
| sha | String |
| is_protected | Boolean |

#### releases {#table-releases}

Grain: 1 row per GitHub release id.

| Column | Type |
|---|---|
| id | BigInteger (PK) |
| repo_id | BigInteger (FK -> repos.id) |
| tag_name | String |
| name | String |
| draft | Boolean |
| prerelease | Boolean |
| created_at | DateTime(tz) |
| published_at | DateTime(tz) |
| author_id | BigInteger (FK -> users.id) |
| body | Text |
| target_commitish | String |

#### events {#table-events}

Grain: normalized event row (unique by `event_key`).

| Column | Type |
|---|---|
| id | Integer (PK) |
| repo_id | BigInteger (FK -> repos.id) |
| occurred_at | DateTime(tz) |
| actor_id | BigInteger (FK -> users.id) |
| subject_type | String |
| subject_id | BigInteger |
| event_type | String |
| object_type | String |
| object_id | BigInteger |
| commit_sha | String |
| payload_json | Text |
| event_key | String (unique) |

#### watermarks {#table-watermarks}

Grain: per (repo_id, resource) incremental cursor.

| Column | Type |
|---|---|
| id | Integer (PK) |
| repo_id | BigInteger (FK -> repos.id) |
| resource | String |
| updated_at | DateTime(tz) |
| etag | String |
| last_modified | String |
| cursor | String |

#### ingestion_gaps {#table-ingestion_gaps}

Grain: one row per detected ingest gap.

| Column | Type |
|---|---|
| id | Integer (PK) |
| repo_id | BigInteger (FK -> repos.id) |
| resource | String |
| url | String |
| page | Integer |
| expected_page | Integer |
| detail | Text |
| detected_at | DateTime(tz) |

#### ingestion_checkpoints {#table-ingestion_checkpoints}

Grain: per (repo_id, flow, stage) checkpoint.

| Column | Type |
|---|---|
| id | Integer (PK) |
| repo_id | BigInteger (FK -> repos.id) |
| flow | String |
| stage | String |
| completed_at | DateTime(tz) |
| details_json | Text |

#### qa_reports {#table-qa_reports}

Grain: per QA report generation.

| Column | Type |
|---|---|
| id | Integer (PK) |
| repo_id | BigInteger (FK -> repos.id) |
| created_at | DateTime(tz) |
| summary_json | Text |

### Interval Tables (Derived from `events`) {#interval-tables}

All interval tables are rebuilt by `packages/ingestion/src/gh_history_ingestion/intervals/rebuild.py`.

- Interval semantics: open interval when `end_event_id` is NULL.

#### issue_state_intervals {#table-issue_state_intervals}

Grain: per (issue_id, state) interval.

| Column | Type |
|---|---|
| id | Integer (PK) |
| issue_id | BigInteger (FK -> issues.id) |
| state | String |
| start_event_id | Integer (FK -> events.id) |
| end_event_id | Integer (FK -> events.id) |

#### issue_content_intervals {#table-issue_content_intervals}

Grain: per issue content version interval.

| Column | Type |
|---|---|
| id | Integer (PK) |
| issue_id | BigInteger (FK -> issues.id) |
| title | String |
| body | Text |
| start_event_id | Integer (FK -> events.id) |
| end_event_id | Integer (FK -> events.id) |

#### issue_label_intervals {#table-issue_label_intervals}

Grain: per (issue_id, label_id) interval.

| Column | Type |
|---|---|
| id | Integer (PK) |
| issue_id | BigInteger (FK -> issues.id) |
| label_id | BigInteger (FK -> labels.id) |
| start_event_id | Integer (FK -> events.id) |
| end_event_id | Integer (FK -> events.id) |

#### issue_assignee_intervals {#table-issue_assignee_intervals}

Grain: per (issue_id, user_id) interval.

| Column | Type |
|---|---|
| id | Integer (PK) |
| issue_id | BigInteger (FK -> issues.id) |
| user_id | BigInteger (FK -> users.id) |
| start_event_id | Integer (FK -> events.id) |
| end_event_id | Integer (FK -> events.id) |

#### issue_milestone_intervals {#table-issue_milestone_intervals}

Grain: per (issue_id, milestone_id) interval.

| Column | Type |
|---|---|
| id | Integer (PK) |
| issue_id | BigInteger (FK -> issues.id) |
| milestone_id | BigInteger (FK -> milestones.id) |
| start_event_id | Integer (FK -> events.id) |
| end_event_id | Integer (FK -> events.id) |

#### pull_request_draft_intervals {#table-pull_request_draft_intervals}

Grain: per (pull_request_id, is_draft) interval.

| Column | Type |
|---|---|
| id | Integer (PK) |
| pull_request_id | BigInteger (FK -> pull_requests.id) |
| is_draft | Boolean |
| start_event_id | Integer (FK -> events.id) |
| end_event_id | Integer (FK -> events.id) |

#### pull_request_head_intervals {#table-pull_request_head_intervals}

Grain: per PR head-sha interval.

| Column | Type |
|---|---|
| id | Integer (PK) |
| pull_request_id | BigInteger (FK -> pull_requests.id) |
| head_sha | String |
| head_ref | String |
| start_event_id | Integer (FK -> events.id) |
| end_event_id | Integer (FK -> events.id) |

#### pull_request_review_request_intervals {#table-pull_request_review_request_intervals}

Grain: per (pull_request_id, reviewer_id) interval.

| Column | Type |
|---|---|
| id | Integer (PK) |
| pull_request_id | BigInteger (FK -> pull_requests.id) |
| reviewer_type | String |
| reviewer_id | BigInteger |
| start_event_id | Integer (FK -> events.id) |
| end_event_id | Integer (FK -> events.id) |

#### comment_content_intervals {#table-comment_content_intervals}

Grain: per comment content version interval.

| Column | Type |
|---|---|
| id | Integer (PK) |
| comment_id | BigInteger (FK -> comments.id) |
| body | Text |
| start_event_id | Integer (FK -> events.id) |
| end_event_id | Integer (FK -> events.id) |

#### review_content_intervals {#table-review_content_intervals}

Grain: per review content version interval.

| Column | Type |
|---|---|
| id | Integer (PK) |
| review_id | BigInteger (FK -> reviews.id) |
| body | Text |
| state | String |
| start_event_id | Integer (FK -> events.id) |
| end_event_id | Integer (FK -> events.id) |

#### object_snapshots {#table-object_snapshots}

Grain: per (event_id, object_type, object_id) snapshot payload row.

| Column | Type |
|---|---|
| id | Integer (PK) |
| event_id | Integer (FK -> events.id) |
| object_type | String |
| object_id | BigInteger |
| payload_json | Text |

## Secondary DB: `examples_index.sqlite` {#secondary-db-examples_index-sqlite}

Schema source:

- `packages/experimentation/src/experimentation/examples_index.py` (`_ensure_schema`)
- Reference schema file: `docs/agent-contracts/examples_index.v1.schema.sql`

Tables:

### meta {#table-examples_index-meta}

Grain: key/value metadata.

| Column | Type |
|---|---|
| key | text (PK) |
| value | text |

### runs {#table-examples_index-runs}

Grain: 1 row per (repo, run_id).

Primary key: (repo, run_id).

| Column | Type |
|---|---|
| repo | text |
| run_id | text |
| run_dir_rel | text |
| generated_at | text |
| cohort_hash | text |
| experiment_spec_hash | text |
| db_max_event_occurred_at | text |
| db_max_watermark_updated_at | text |
| manifest_json_sha256 | text |
| report_json_sha256 | text |
| per_pr_jsonl_sha256 | text |

### examples {#table-examples_index-examples}

Grain: 1 row per (repo, run_id, pr_number).

Primary key: (repo, run_id, pr_number).

| Column | Type |
|---|---|
| repo | text |
| run_id | text |
| pr_number | integer |
| cutoff | text |
| truth_status | text |
| missing_issue | integer |
| missing_ai_disclosure | integer |
| missing_provenance | integer |
| merged | integer |
| primary_policy | text |
| routers_json | text |
| artifact_paths_json | text |
| indexed_at | text |
