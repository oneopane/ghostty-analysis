# Codebase Map Pack - Generation Report

This report summarizes what was extracted confidently from code, what remains ambiguous, and what changes would improve future automated mapping.

## Confident Inferences (Backed by Code)

- Workspace packages and entrypoints are defined in package `pyproject.toml` files and mounted by `packages/cli/src/repo_cli/cli.py`.
- Primary persistent store is `data/github/<owner>/<repo>/history.sqlite` with ORM schema in `packages/ingestion/src/gh_history_ingestion/storage/schema.py`.
- Interval tables are derived from `events` by `packages/ingestion/src/gh_history_ingestion/intervals/rebuild.py`.
- Evaluation produces a stable run directory under `data/github/<owner>/<repo>/eval/<run_id>/` (paths defined in both `repo_routing.artifacts.paths` and `evaluation_harness.paths`).
- Truth extraction is coverage-aware and explicitly models `unknown_due_to_ingestion_gap` vs `no_post_cutoff_response` (`packages/evaluation/src/evaluation_harness/truth.py`).
- Metrics implemented are routing agreement (`hit@k`, `mrr`), gates correlation, and queue metrics (`ttfr_seconds`) (`packages/evaluation/src/evaluation_harness/metrics/*`).
- Experimentation orchestrates eval runs and derives cross-run searchable indexes in `examples_index.sqlite` (`packages/experimentation/src/experimentation/examples_index.py`).

## Ambiguities / Gaps

- Feature extractor registry exists, but built-in routers do not currently require it; feature artifacts are only written when a router uses `PipelinePredictor` (`packages/evaluation/src/evaluation_harness/runner_per_pr.py`). This makes "canonical features" optional rather than guaranteed.
- Some truth policy specs exist in `truth_policy.py` (e.g. `merger_v1`, `hybrid_owner_v1`) but are gated as unavailable in `truth_with_policy`, so policy catalog and effective label set can diverge.
- Task specs under `docs/attention-routing/tasks/` describe label windows (e.g. 14d) that differ from the evaluation harness default truth window (60 minutes). Without explicit configuration, labels/metrics may not match task docs.
- The repo does not use a migration system for SQLite; schema evolution history is not encoded as migrations.

## Recommended Improvements

- Add a first-class "dataset registry" (code + JSON) that declares:
  - dataset names/paths
  - grains
  - owning package
  - stability guarantees
- Make feature emission explicit and mandatory for routers expected to be evaluated on features (e.g. enforce `PipelinePredictor` for certain router ids or add a feature export hook).
- Add schema versioning for `history.sqlite` (pragma user_version + explicit migrations), and emit the schema version into `manifest.json`.
- Align truth windows with task specs by encoding task->policy window mappings in code (or embedding truth window + policy hash into cohort/spec artifacts).
- Expand contract tests to assert package boundary rules (e.g. no inference->ingestion imports) and to validate artifact directory shapes.
