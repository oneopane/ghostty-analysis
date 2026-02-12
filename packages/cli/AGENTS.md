# PROJECT KNOWLEDGE BASE

## OVERVIEW
Unified CLI package exposing the `repo` command and wiring ingestion, experimentation, inference, and evaluation subcommands.

## STRUCTURE
```
packages/cli/
└── src/repo_cli/
    ├── cli.py                 # dedicated repo root app + subcommand composition
    ├── unified_experiment.py  # compatibility shim (deprecated)
    └── marimo_components.py   # compatibility shim (deprecated)
```

## BEHAVIOR NOTES
- Root command is owned by `repo_cli` and mounts ingestion under `repo ingestion ...`.
- `inference` and `evaluation` groups are mounted as optional packages.
- If optional import fails, CLI exposes degraded command groups that print a clear failure reason and exit non-zero.

## COMMANDS
```bash
uv run --project packages/cli repo --help
uv run --project packages/cli repo ingestion --help
```
