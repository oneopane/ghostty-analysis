# 027 - Document baseline limitations (CODEOWNERS leakage warnings)

- [x] Done

## Goal
Prevent misleading conclusions from leaky or mis-specified baselines.

## Work
- Document when CODEOWNERS is considered leaky (e.g. using repo HEAD).
- Document which baselines require a local checkout and git.

## Files
Create:
- `packages/evaluation/docs/baselines.md`

## Acceptance Criteria
- Reports include baseline caveats and required inputs.
