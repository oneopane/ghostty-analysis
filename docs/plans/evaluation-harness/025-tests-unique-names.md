# 025 - Ensure unique test module names across packages

- [x] Done

## Goal
Avoid pytest import collisions when running tests from the monorepo root.

## Work
- Ensure test module basenames are unique per package.

## Files
Touch (as needed):
- `packages/*/tests/*.py`

## Acceptance Criteria
- `uv run pytest` at repo root succeeds without collection errors.
