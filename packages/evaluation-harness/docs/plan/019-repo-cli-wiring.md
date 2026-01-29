# 019 - Validate unified CLI wiring

- [x] Done

## Goal
Ensure the unified `repo` CLI correctly mounts routing and evaluation subcommands.

## Work
- Confirm `repo routing ...` and `repo eval ...` work from a fresh environment.
- Ensure naming remains stable as packages evolve.

## Files
Touch (only if needed):
- `packages/repo-cli/src/repo_cli/cli.py`

## Acceptance Criteria
- `repo --help` shows `routing` and `eval` command groups.
