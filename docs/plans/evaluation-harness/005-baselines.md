# 005 - Implement offline baselines behind Router API

- [ ] Done

## Goal
Provide minimal, credible baselines that do not require GitHub API calls.

## Work
- Mentions baseline: route to explicitly mentioned `@user`/`@org/team` in PR body.
- Popularity baseline: route to top reviewers by exponentially decayed review counts (default candidate history window: last 180 days as-of cutoff).
- CODEOWNERS baseline (optional): use a local checkout + git to read CODEOWNERS as-of PR base SHA.

## Files
Create:
- `packages/inference/src/repo_routing/router/baselines/__init__.py`
- `packages/inference/src/repo_routing/router/baselines/mentions.py`
- `packages/inference/src/repo_routing/router/baselines/popularity.py`
- `packages/inference/src/repo_routing/router/baselines/codeowners.py`

## Acceptance Criteria
- Baselines return a `RouteResult` with transparent reasons.
- CODEOWNERS baseline is explicitly labeled as leaky unless it reads CODEOWNERS as-of base SHA.
