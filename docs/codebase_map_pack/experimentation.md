# Experimentation Layer

This repo provides:

- A unified experiment runner (cohort/spec/run/summarize/promote/index) under `repo experiment ...`.
- Marimo notebooks for interactive orchestration, analysis, and auditing.
- A cross-run index DB (`examples_index.sqlite`) for searchable per-PR examples.

## Unified Experiment Workflow

Command wiring:

- `packages/experimentation/src/experimentation/unified_experiment.py`

Core orchestration:

- `packages/experimentation/src/experimentation/workflow_run.py` (`experiment_run`)

Key artifacts written into `data/github/<owner>/<repo>/eval/<run_id>/`:

- `cohort.json` and `experiment.json` copies
- `experiment_manifest.json` (cutoffs, router ids, optional prefetch summary)
- `manifest.json`, `report.json`, `report.md`, `per_pr.jsonl` (evaluation harness)
- `run_summary.json` + optional compare artifacts

## Artifact Loading Patterns

Canonical file readers:

- `packages/experimentation/src/workflow/reports.py`:
  - loads `report.json`
  - loads `per_pr.jsonl`
  - loads `experiment_manifest.json`

Cross-run example indexing:

- `packages/experimentation/src/experimentation/examples_index.py`
  - reads run directory artifacts offline
  - upserts `runs` and `examples` rows into `examples_index.sqlite`

Pinned artifact prefetch (optional network use):

- `packages/experimentation/src/experimentation/workflow_artifacts.py`
  - discovers PR `base_sha` as-of cutoff
  - checks `pinned_artifact_path(...)` existence
  - fetches missing via `gh_history_ingestion.repo_artifacts.fetcher.fetch_pinned_repo_artifacts_sync`

## Notebooks

Marimo notebooks live under:

- `notebooks/` (end-to-end pipeline UI, component demos, audits)
- `experiments/marimo/` (router/config exploration, boundary membership experiments)

Notable notebooks/scripts:

- `notebooks/ghostty_marimo_pipeline.py` (orchestrates ingest/export/eval via CLI calls)
- `experiments/extract/export_v0.py` (SQLite -> Parquet export)
- `experiments/marimo/stewards_v0.py` (reads Parquet exports + emits stewards config)
