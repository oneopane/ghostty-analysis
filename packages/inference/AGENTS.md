# PROJECT KNOWLEDGE BASE

## OVERVIEW
Post-ingest routing/inference artifacts, baselines, and heuristics built from local history databases.

## STRUCTURE
```
packages/inference/
├── src/repo_routing/
│   ├── cli/
│   ├── router/
│   ├── artifacts/
│   ├── predictor/
│   ├── scoring/
│   ├── inputs/
│   └── policy/
└── tests/

experiments/
├── extract/
├── configs/
└── marimo/
```

## COMMANDS
```bash
uv run --project packages/inference inference info --repo owner/name
uv run --project packages/inference inference build-artifacts --repo owner/name --run-id run1
uv run --project packages/inference python experiments/extract/export_v0.py --repo owner/name --export-run-id run1
```
