# PROJECT KNOWLEDGE BASE

## OVERVIEW
Experiment workflow package for cohort/spec management, quality gates, promotion checks, and marimo helper components.

## STRUCTURE
```
packages/experimentation/
└── src/experimentation/
    ├── unified_experiment.py    # cohort/experiment/profile/doctor commands
    └── marimo_components.py     # reusable marimo UI components
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Unified experiment flows | packages/experimentation/src/experimentation/unified_experiment.py | cohort/spec/run/diff/profile/doctor |
| Notebook UI helpers | packages/experimentation/src/experimentation/marimo_components.py | ingestion + analysis reusable panels |

## COMMANDS
```bash
uv run --project packages/cli repo experiment --help
uv run --project packages/cli repo cohort --help
uv run --project packages/cli repo profile --help
```
