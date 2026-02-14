# Contracts

This repo treats package boundaries as operational contracts. The most important contracts are:

## Data Contracts

- `history.sqlite` schema is a shared contract across ingestion, inference, and evaluation.
  - Owned by: `packages/ingestion`.
  - Read by: `packages/inference`, `packages/evaluation`, and export scripts.

- Cutoff safety:
  - `repo_routing.inputs.builder.build_pr_input_bundle` uses `HistoryReader(..., strict_as_of=True)`.
  - Evaluation enforces stale-cutoff guard when `strict_streaming_eval=True` in `packages/evaluation/src/evaluation_harness/runner_prepare.py`.

## API Surface Contracts

- Stable inference API module: `packages/inference/src/repo_routing/api.py`
  - Intended for external packages (experimentation) to avoid deep imports.

- Stable evaluation API module: `packages/evaluation/src/evaluation_harness/api.py`
  - Used by experimentation workflows.

## Package Dependency Rules (Observed)

- `repo_cli` imports and mounts other CLIs.
- `experimentation` depends on `evaluation_harness` and `repo_routing`, and optionally triggers ingestion-side pinned artifact fetching.
- `evaluation_harness` depends on `repo_routing` for router loading and artifact writing.
- `repo_routing` and `gh_history_ingestion` are independent (no inference->ingestion import).

## Allowed Artifact Exchange

- Ingestion -> others: `history.sqlite`, plus optional pinned repo artifacts under `repo_artifacts/<base_sha>/...`.
- Inference -> evaluation: routers + artifact writer paths (writes into eval run dir).
- Evaluation -> experimentation: eval run dir artifacts (`report.json`, `per_pr.jsonl`, `manifest.json`).
- Experimentation -> indexing: `examples_index.sqlite` derived from eval run dir.
