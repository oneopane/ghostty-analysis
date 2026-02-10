# PROJECT KNOWLEDGE BASE

**Generated:** 2026-02-10 12:58 PST
**Commit:** 97445f7
**Branch:** HEAD

## OVERVIEW
Python uv-workspace monorepo for repository ingestion, routing artifacts, and evaluation, with a unified CLI.

## STRUCTURE
```
./
├── data/          # local artifacts, sqlite, eval outputs
├── docs/          # architecture, plans, and process docs
├── notebooks/     # marimo notebooks and demos
├── packages/      # workspace packages (src/ layout)
├── scripts/       # validation scripts
├── pyproject.toml # uv workspace members
└── uv.lock
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Ingest GitHub history | packages/repo-ingestion/src/gh_history_ingestion | CLI and ingest flows |
| Generate routing artifacts | packages/repo-routing/src/repo_routing | baselines, artifacts, scoring |
| Run evaluation harness | packages/evaluation-harness/src/evaluation_harness | runner, metrics, reporting |
| Unified CLI wiring | packages/repo-cli/src/repo_cli/cli.py | adds routing/eval subcommands |
| Attention routing docs | docs/attention-routing | architecture + registry/checklist |
| Eval harness plan | docs/plans/evaluation-harness | atomic task files + checklist |
| Feature validation | scripts/validate_feature_stack.sh | targeted pytest suites |

## CODE MAP
| Symbol | Type | Location | Refs | Role |
|--------|------|----------|------|------|
| app | Typer app | packages/repo-ingestion/src/gh_history_ingestion/cli/app.py | 7 | repo-ingestion CLI commands |
| app | Typer app | packages/repo-routing/src/repo_routing/cli/app.py | 5 | repo-routing CLI commands |
| app | Typer app | packages/evaluation-harness/src/evaluation_harness/cli/app.py | 9 | evaluation-harness CLI commands |
| backfill_repo | async fn | packages/repo-ingestion/src/gh_history_ingestion/ingest/backfill.py | 0 | full history backfill |
| ArtifactWriter | dataclass | packages/repo-routing/src/repo_routing/artifacts/writer.py | 0 | write route/snapshot artifacts |
| build_pr_input_bundle | fn | packages/repo-routing/src/repo_routing/inputs/builder.py | 0 | assemble PR inputs |
| run_streaming_eval | fn | packages/evaluation-harness/src/evaluation_harness/runner.py | 0 | streaming evaluation runner |

## CONVENTIONS
- Use `uv` workspace; prefer `uv run --project packages/<pkg> ...` for commands.
- Packages use `src/` layout; pytest config sets `pythonpath = ["src"]`.
- CLIs use Typer; entry points set in each package `pyproject.toml`.

## ANTI-PATTERNS (THIS PROJECT)
- None documented at the repo level.

## UNIQUE STYLES
- `docs/attention-routing/architecture.md` is current; related task/planning docs there are historical.
- `docs/attention-routing/tasks/README.md` requires every task to beat a non-ML baseline before promotion.
- `docs/attention-routing/traceability` is the operational source of truth for transcript→decision→implementation.
- `docs/plans/evaluation-harness` uses atomic task files; checkboxes in the index mark completion.

## COMMANDS
```bash
uv venv
uv pip install -e .

uv run --project packages/repo-ingestion repo-ingestion --help
uv run --project packages/repo-routing repo-routing --help
uv run --project packages/evaluation-harness evaluation-harness --help
uv run --project packages/repo-cli repo --help
```

## NOTES
- Default data paths: `data/github/<owner>/<repo>/history.sqlite` and eval outputs under `data/github/<owner>/<repo>/eval/<run_id>/`.
- `scripts/validate_feature_stack.sh` expects `./.venv/bin/pytest` (not `uv run`).
- Repo supports Jujutsu (`jj`) workflows; Git is compatible but avoid `git commit` unless required.
