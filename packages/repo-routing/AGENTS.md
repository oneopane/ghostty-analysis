# PROJECT KNOWLEDGE BASE

## OVERVIEW
Post-ingest routing artifacts, baselines, and heuristics built from local history databases.

## STRUCTURE
```
packages/repo-routing/
├── src/repo_routing/
│   ├── cli/                                # Typer CLI
│   ├── router/                             # baselines + explain helpers
│   ├── artifacts/                          # artifact builders + writer
│   ├── predictor/                          # feature extraction + scoring
│   ├── scoring/                            # scoring helpers
│   ├── inputs/                             # input bundle builders
│   └── policy/                             # labels + policy metadata
├── experiments/                            # export + marimo notebooks
└── tests/
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| CLI commands | packages/repo-routing/src/repo_routing/cli/app.py | info/snapshot/route/build-artifacts |
| Baselines | packages/repo-routing/src/repo_routing/router/baselines | mentions/popularity/codeowners/stewards |
| Artifact writers | packages/repo-routing/src/repo_routing/artifacts/writer.py | snapshot + route outputs |
| Feature extraction | packages/repo-routing/src/repo_routing/predictor | feature builders + scorers |
| Input bundles | packages/repo-routing/src/repo_routing/inputs | DB access + models |
| Experiments | packages/repo-routing/experiments | export scripts + marimo notebooks |

## CONVENTIONS
- Baseline names are normalized to: mentions, popularity, codeowners, stewards.
- `--config` is required when baseline includes `stewards`.

## ANTI-PATTERNS (THIS PACKAGE)
- None documented.

## COMMANDS
```bash
uv run --project packages/repo-routing repo-routing info --repo owner/name
uv run --project packages/repo-routing repo-routing build-artifacts --repo owner/name --run-id run1
uv run --project packages/repo-routing python packages/repo-routing/experiments/extract/export_v0.py --repo owner/name --export-run-id run1
```
