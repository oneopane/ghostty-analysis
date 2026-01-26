# 007 - Extend repo-routing CLI commands

- [ ] Done

## Goal
Provide offline commands to build artifacts and inspect routing decisions locally.

## Work
- Add `repo routing build-artifacts`.
- Add `repo routing route --pr <num>` for debugging explanations.

## Files
Touch:
- `packages/repo-routing/src/repo_routing/cli/app.py`

Create:
- `packages/repo-routing/src/repo_routing/cli/build_artifacts.py`
- `packages/repo-routing/src/repo_routing/cli/route.py`

## Acceptance Criteria
- Commands only read local DB + local checkout (if provided).
- Output includes evidence-backed reasons.
