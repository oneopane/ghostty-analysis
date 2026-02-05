# repo-routing

Post-ingest routing artifacts and heuristics.

This package is intentionally separate from `repo-ingestion`:

- `repo-ingestion` builds the canonical history database.
- `repo-routing` reads that database and generates artifacts used for routing and evaluation.

Default per-repo DB location is:

`data/github/<owner>/<repo>/history.sqlite`

This package does not call GitHub APIs. It only reads local history databases.

Use via the unified CLI:

`repo routing --help`

## Example: export + stewards eval (offline)

Export Parquet facts:

```
uv run --project packages/repo-routing python packages/repo-routing/experiments/extract/export_v0.py \
  --repo owner/name \
  --export-run-id run1 \
  --from 2024-01-01T00:00:00Z \
  --end-at 2024-02-01T00:00:00Z \
  --include-text \
  --include-truth
```

Run the stewards router in the evaluation harness:

```
uv run --project packages/evaluation-harness evaluation-harness run \
  --repo owner/name \
  --router stewards \
  --config packages/repo-routing/experiments/configs/v0.json \
  --pr 123
```

Explore exports and write configs in marimo:

```
uv run --project packages/repo-routing marimo run packages/repo-routing/experiments/marimo/stewards_v0.py
```
