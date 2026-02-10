# PROJECT KNOWLEDGE BASE

## OVERVIEW
Offline evaluation harness for routing and policy signals, consuming repo-routing artifacts and history DBs.

## STRUCTURE
```
packages/evaluation-harness/
├── src/evaluation_harness/
│   ├── cli/                                # Typer CLI
│   ├── runner.py                            # streaming eval runner
│   ├── metrics/                             # routing agreement, gates, queue
│   ├── reporting/                           # markdown/json formatters
│   ├── sampling.py                          # deterministic sampling
│   ├── cutoff.py                            # cutoff policies
│   ├── store/                               # filesystem stores
│   └── config.py                            # eval run config
└── tests/
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| CLI commands | packages/evaluation-harness/src/evaluation_harness/cli/app.py | run/show/explain/list |
| Streaming evaluator | packages/evaluation-harness/src/evaluation_harness/runner.py | main execution flow |
| Cutoff policy | packages/evaluation-harness/src/evaluation_harness/cutoff.py | per-PR cutoff logic |
| Metrics | packages/evaluation-harness/src/evaluation_harness/metrics | routing agreement, gates, queue |
| Reporting | packages/evaluation-harness/src/evaluation_harness/reporting | markdown/json outputs |
| Run outputs | packages/evaluation-harness/src/evaluation_harness/paths.py | output paths |

## CONVENTIONS
- Router configs may be passed via `--router-config` (positional or key=value).

## ANTI-PATTERNS (THIS PACKAGE)
- None documented.

## COMMANDS
```bash
uv run --project packages/evaluation-harness evaluation-harness run --repo owner/name
uv run --project packages/evaluation-harness evaluation-harness show --repo owner/name --run-id run1
uv run --project packages/evaluation-harness evaluation-harness explain --repo owner/name --run-id run1 --pr 123
```
