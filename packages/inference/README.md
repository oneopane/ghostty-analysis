# inference

## Start here

For the canonical end-to-end experiment path through the unified CLI:

- `../../docs/examples/e2e-unified-cli.md`

Post-ingest routing/inference artifacts and heuristics.

This package is intentionally separate from ingestion:

- `ingestion` builds the canonical history database.
- `inference` reads local history and emits deterministic routing artifacts.

Default DB location:

`data/github/<owner>/<repo>/history.sqlite`

Use via unified CLI:

`repo inference --help`

## Example: export + stewards eval

```bash
uv run --project packages/inference python experiments/extract/export_v0.py \
  --repo owner/name \
  --export-run-id run1 \
  --from 2024-01-01T00:00:00Z \
  --end-at 2024-02-01T00:00:00Z \
  --include-text \
  --include-truth
```

```bash
uv run --project packages/evaluation evaluation run \
  --repo owner/name \
  --router stewards \
  --config experiments/configs/v0.json \
  --pr 123
```

```bash
uv run --project packages/inference marimo run experiments/marimo/stewards_v0.py
```
