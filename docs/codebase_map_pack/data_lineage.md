# Data Lineage

This section documents how raw GitHub data becomes normalized SQLite, then cutoff-safe artifacts, then evaluation outputs and experiment indexes.

## Lineage Diagram (Mermaid) {#lineage-diagram-mermaid}

```mermaid
flowchart LR
  GH[GitHub REST API] --> ING[gh_history_ingestion ingest/backfill/incremental]
  ING --> HDB[(history.sqlite)]

  HDB --> INT[intervals/rebuild.py\n*interval tables]
  HDB --> ROUTE[repo_routing routers\nroute()]
  HDB --> INPUTS[repo_routing.inputs.builder\nPRInputBundle strict as-of]

  INPUTS --> ROUTE
  ROUTE --> RUNART[(eval run artifacts\nprs/<pr>/routes/*.json)]
  INPUTS --> SNAP[(eval run artifacts\nprs/<pr>/snapshot.json + inputs.json)]

  HDB --> TRUTH[evaluation_harness.truth\nTruthDiagnostics]
  TRUTH --> EVALRUN[(eval run dir\nreport.json report.md per_pr.jsonl manifest.json)]
  RUNART --> EVALRUN
  SNAP --> EVALRUN

  EVALRUN --> INDEX[experimentation.examples_index\nexamples_index.sqlite]

  HDB --> EXPORT[experiments/extract/export_v0.py]
  EXPORT --> PAR[(Parquet datasets\nprs.parquet pr_files.parquet pr_activity.parquet ...)]
```

## Dataset Catalog

| Dataset | Type | Grain | Source | Known By Time |
|---|---|---|---|---|
| `data/github/<owner>/<repo>/history.sqlite` | normalized | mixed (see `schemas.md`) | `gh_history_ingestion` | up to ingestion horizon (depends on run) |
| Interval tables in `history.sqlite` | normalized | per (entity, interval) | `gh_history_ingestion/intervals/rebuild.py` derived from `events` | as-of semantics via `(start_event_id, end_event_id)` |
| Pinned repo artifacts under `.../repo_artifacts/<base_sha>/...` | raw | per file path per base SHA | `gh_history_ingestion.repo_artifacts.fetcher` (called via experimentation prefetch) | immutable by construction (anchored to base SHA) |
| Boundary model artifacts under `.../artifacts/routing/boundary_model/<strategy>/<cutoff_key>/...` | model_input | per (repo, cutoff_key, strategy) | `repo_routing.boundary.pipeline.write_boundary_model_artifacts` | cutoff-key anchored |
| Eval run directory `.../eval/<run_id>/` | reporting | per run | `evaluation_harness` runner emitters | produced at run time |
| Per-PR artifacts `.../eval/<run_id>/prs/<pr_number>/...` | prediction/feature | per PR per router | `repo_routing.artifacts.writer.ArtifactWriter` (used by evaluation) | cutoff-safe; router-dependent |
| `data/github/<owner>/<repo>/examples_index.sqlite` | normalized | per (repo, run_id, pr_number) | `experimentation.examples_index.index_run` | after eval run exists |
| Exported Parquet under `data/exports/<owner>/<repo>/<export_run_id>/` | model_input | per PR / per file / per activity event | `experiments/extract/export_v0.py` | cutoff-safe for snapshot tables; activity window is explicit |

Links:

- Schemas: `docs/codebase_map_pack/schemas.md`
- Features: `docs/codebase_map_pack/features.md`
