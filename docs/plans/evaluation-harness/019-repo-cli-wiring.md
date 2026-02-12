# 019 - Validate unified CLI wiring

- [x] Done

## Goal
Ensure the unified `repo` CLI correctly mounts inference and evaluation subcommands.

## Work
- Confirm `repo inference ...` and `repo evaluation ...` work from a fresh environment.
- Ensure naming remains stable as packages evolve.

## Files
Touch (only if needed):
- `packages/cli/src/repo_cli/cli.py`

## Acceptance Criteria
- `repo --help` shows `inference` and `evaluation` command groups.
