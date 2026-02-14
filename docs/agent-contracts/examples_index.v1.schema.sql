-- examples_index.sqlite schema (v1)
--
-- Purpose:
--   Cross-run index of per-PR artifacts and gate-relevant statuses.
--   Build strictly from on-disk run artifacts (per_pr.jsonl + run-root files).
--
-- Compatibility:
--   - Additive columns/tables are non-breaking.
--   - Breaking changes require a schema_version bump stored in meta.

create table if not exists meta (
  key text primary key,
  value text not null
);

create table if not exists runs (
  repo text not null,
  run_id text not null,
  run_dir_rel text not null,
  generated_at text,
  cohort_hash text,
  experiment_spec_hash text,
  db_max_event_occurred_at text,
  db_max_watermark_updated_at text,
  manifest_json_sha256 text,
  report_json_sha256 text,
  per_pr_jsonl_sha256 text,
  primary key (repo, run_id)
);

create table if not exists examples (
  repo text not null,
  run_id text not null,
  pr_number integer not null,
  cutoff text,
  truth_status text,
  missing_issue integer,
  missing_ai_disclosure integer,
  missing_provenance integer,
  merged integer,
  primary_policy text,
  routers_json text,
  artifact_paths_json text,
  indexed_at text,
  primary key (repo, run_id, pr_number),
  foreign key (repo, run_id) references runs(repo, run_id) on delete cascade
);

create index if not exists idx_examples_repo_pr on examples(repo, pr_number);
create index if not exists idx_examples_repo_truth_status on examples(repo, truth_status);
create index if not exists idx_examples_repo_missing_issue on examples(repo, missing_issue);
