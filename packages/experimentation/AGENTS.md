# PROJECT KNOWLEDGE BASE

## OVERVIEW
Experiment workflow package for cohort/spec management, quality gates, promotion checks, and marimo helper components.

## STRUCTURE
```
packages/experimentation/
└── src/experimentation/
    ├── unified_experiment.py    # command registration/root Typer groups
    ├── workflow_cohort.py       # cohort creation and hashing
    ├── workflow_spec.py         # experiment spec initialization
    ├── workflow_run.py          # eval execution + manifests + quality post-processing
    ├── workflow_eval.py         # show/list/explain wrappers
    ├── workflow_profile.py      # repo-profile artifact build flow
    ├── workflow_diff.py         # run-to-run metric diffs
    ├── workflow_quality.py      # promotion gates and report sync
    ├── workflow_doctor.py       # diagnostics and preflight checks
    ├── workflow_helpers.py      # shared parsing/io/hash/cutoff helpers
    ├── workflow/reports.py      # report/per_pr context readers (canonical path)
    └── marimo_components.py     # reusable marimo UI components
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Unified command wiring | packages/experimentation/src/experimentation/unified_experiment.py | mounts cohort/experiment/profile/doctor |
| End-to-end run flow | packages/experimentation/src/experimentation/workflow_run.py | cohort/spec validation, eval invoke, manifest |
| Cohort/spec flows | packages/experimentation/src/experimentation/workflow_cohort.py / workflow_spec.py | artifact creation + hashes |
| Diff and quality gates | packages/experimentation/src/experimentation/workflow_diff.py / workflow_quality.py | promotion logic |
| Notebook UI helpers | packages/experimentation/src/experimentation/marimo_components.py | ingestion + analysis reusable panels |

## COMMANDS
```bash
uv run --project packages/cli repo experiment --help
uv run --project packages/cli repo cohort --help
uv run --project packages/cli repo profile --help
```
