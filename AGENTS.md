# PROJECT KNOWLEDGE BASE

**Generated:** 2026-02-11 16:15 PST
**Branch:** HEAD

## OVERVIEW
Python uv-workspace monorepo for repository ingestion, inference/routing artifacts, experimentation workflows, evaluation, and a unified CLI.

## STRUCTURE
```
./
├── data/          # local artifacts, sqlite, eval outputs
├── docs/          # architecture, plans, and process docs
├── notebooks/     # marimo notebooks and demos
├── experiments/   # reproducible experiment configs/extract scripts/notebooks
├── packages/      # workspace packages (src/ layout)
├── scripts/       # validation scripts
├── pyproject.toml # uv workspace members
└── uv.lock
```

## WORKSPACE PACKAGES
- `packages/core`             # shared SDLC ids/hashing/types/stores
- `packages/ingestion`        # GitHub -> history.sqlite
- `packages/inference`        # cutoff-safe snapshots, routers, artifact writing
- `packages/experimentation`  # cohort/spec flow, quality gates, marimo helpers
- `packages/evaluation`       # streaming eval, truth policies, metrics, reporting
- `packages/cli`              # unified `repo` command surface

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Ingest GitHub history | packages/ingestion/src/gh_history_ingestion | CLI and ingest flows |
| Run inference/routing artifacts | packages/inference/src/repo_routing | baselines, artifacts, scoring |
| Unified experiment workflows | packages/experimentation/src/experimentation/unified_experiment.py | cohort/spec/run/diff/profile/doctor |
| Run evaluation harness | packages/evaluation/src/evaluation_harness | runner, metrics, reporting |
| Unified CLI wiring | packages/cli/src/repo_cli/cli.py | mounts ingestion + experimentation + routing + eval |
| Attention routing docs | docs/attention-routing | architecture + registry/checklist |
| Eval harness plan | docs/plans/evaluation-harness | atomic task files + checklist |
| Feature validation | scripts/validate_feature_stack.sh | targeted pytest suites |

## CONVENTIONS
- Use `uv` workspace; prefer `uv run --project packages/<pkg> ...` for commands.
- Packages use `src/` layout; pytest config sets `pythonpath = ["src"]`.
- CLIs use Typer; entry points are set in each package `pyproject.toml`.
- Keep import modules stable for now (`gh_history_ingestion`, `repo_routing`, `evaluation_harness`, `repo_cli`) while package names are the new core names.

## UNIQUE STYLES
- `docs/attention-routing/architecture.md` is current; related task/planning docs there are historical.
- `docs/attention-routing/tasks/README.md` requires every task to beat a non-ML baseline before promotion.
- `docs/attention-routing/traceability` is the operational source of truth for transcript→decision→implementation.
- `docs/plans/evaluation-harness` uses atomic task files; checkboxes in the index mark completion.

## COMMANDS
```bash
uv venv
uv sync

uv run --project packages/ingestion ingestion --help
uv run --project packages/inference inference --help
uv run --project packages/evaluation evaluation --help
uv run --project packages/cli repo --help
```

## NOTES
- Default data paths: `data/github/<owner>/<repo>/history.sqlite` and eval outputs under `data/github/<owner>/<repo>/eval/<run_id>/`.
- `scripts/validate_feature_stack.sh` expects `./.venv/bin/pytest` (not `uv run`).
- Repo supports Jujutsu (`jj`) workflows; Git is compatible but avoid `git commit` unless required.
