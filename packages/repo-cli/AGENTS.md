# PROJECT KNOWLEDGE BASE

## OVERVIEW
Unified CLI that wires repo-ingestion, repo-routing, and evaluation-harness into one command.

## STRUCTURE
```
packages/repo-cli/
└── src/repo_cli/cli.py                      # Typer app wiring
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| CLI wiring | packages/repo-cli/src/repo_cli/cli.py | adds routing/eval subcommands |

## CONVENTIONS
- This package is a thin wrapper; it imports apps from other packages.

## ANTI-PATTERNS (THIS PACKAGE)
- None documented.

## COMMANDS
```bash
uv run --project packages/repo-cli repo --help
```
