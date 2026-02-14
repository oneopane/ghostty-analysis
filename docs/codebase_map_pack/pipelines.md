# Pipelines

This repo primarily runs as manually-invoked CLI pipelines (plus lightweight CI checks).

## Ingestion Pipeline {#pipeline-ingestion}

Entrypoints:

- `uv run --project packages/ingestion ingestion ingest --repo owner/name`
- `uv run --project packages/ingestion ingestion incremental --repo owner/name`
- `uv run --project packages/ingestion ingestion pull-requests --repo owner/name --from ... --end-at ... [--with-truth]`

```mermaid
flowchart TD
  A[GitHub REST API] --> B[backfill_repo / incremental_update / backfill_pull_requests]
  B --> C[upsert_* + insert_event]\n
  C --> D[(history.sqlite tables)]
  B --> E[intervals/rebuild_intervals]\n
  E --> F[(interval tables)]
  B --> G[qa report + ingestion gaps + checkpoints]\n
  G --> D
```

Scheduling:

- No scheduler in-repo; run ad-hoc.
- CI runs docs + package smoke/tests: `.github/workflows/docs-checks.yml`.

## Inference / Artifact Pipeline {#pipeline-inference}

Entrypoints:

- `uv run --project packages/inference inference build-artifacts --repo owner/name --run-id <run_id> [--from/--end-at|--pr]`
- `uv run --project packages/inference inference boundary build --repo owner/name --as-of <ISO>`

```mermaid
flowchart TD
  DB[(history.sqlite)] --> SNAP[build_pr_snapshot_artifact]\n
  DB --> ROUTE[build_route_artifact / router.route]\n
  SNAP --> WRITE[ArtifactWriter writes under eval/<run_id>/prs/<pr>/]\n
  ROUTE --> WRITE

  DB --> B[write_boundary_model_artifacts]\n
  B --> BOUT[(boundary_model.json + memberships.parquet + manifest.json)]
```

## Evaluation Pipeline {#pipeline-evaluation}

Entrypoint:

- `uv run --project packages/evaluation evaluation run --repo owner/name --router <rid>... [--from/--end-at|--pr]`

```mermaid
flowchart TD
  DB[(history.sqlite)] --> PREP[prepare_eval_stage]\n
  PREP --> PRS[per_pr_evaluate_stage]\n
  PRS --> ART[write per-PR artifacts]\n
  PRS --> TRUTH[truth_with_policy]\n
  PRS --> MET[per_pr metrics: routing + gates + queue]\n
  MET --> AGG[aggregate_eval_stage]\n
  AGG --> EMIT[manifest.json report.json report.md per_pr.jsonl]\n
  EMIT --> RUN[(eval/<run_id>/)]
```

## Experimentation (Unified Runner) {#pipeline-experimentation}

Entrypoints (mounted under `repo`):

- `uv run --project packages/cli repo cohort create ...`
- `uv run --project packages/cli repo experiment init ...`
- `uv run --project packages/cli repo experiment run ...`
- `uv run --project packages/cli repo experiment summarize ...`
- `uv run --project packages/cli repo experiment index-all ...`

```mermaid
flowchart TD
  COH[cohort.json + hash] --> RUN[experiment_run]
  SPEC[experiment spec json + hash] --> RUN
  RUN --> PREF[prefetch pinned artifacts (optional)]
  RUN --> EVAL[evaluation_harness.api.run]\n
  EVAL --> OUT[(eval/<run_id>/)]
  OUT --> POST[quality gates + promotion eval]\n
  POST --> OUT
  OUT --> SUM[run_summary.json + compare_summary.json]\n
  SUM --> OUT
  OUT --> IDX[examples_index.sqlite]\n
  IDX --> OUT
```

## Export Pipeline (SQLite -> Parquet) {#pipeline-export}

Entrypoint:

- `uv run --project packages/inference python experiments/extract/export_v0.py --repo owner/name --export-run-id <id> ...`

Outputs:

- `prs.parquet`, `pr_files.parquet`, `pr_activity.parquet`
- Optional: `prs_text.parquet`, `truth_behavior.parquet`, `truth_intent.parquet`
- `export_manifest.json`
