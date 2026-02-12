# 007 - Extend inference CLI commands

- [ ] Done

## Goal
Provide offline commands to build artifacts and inspect routing decisions locally.

## Work
- Add `repo inference build-artifacts`.
- Add `repo inference route --pr <num>` for debugging explanations.

## Files
Touch:
- `packages/inference/src/repo_routing/cli/app.py`

Create:
- `packages/inference/src/repo_routing/cli/build_artifacts.py`
- `packages/inference/src/repo_routing/cli/route.py`

## Acceptance Criteria
- Commands only read local DB + local checkout (if provided).
- Output includes evidence-backed reasons.
