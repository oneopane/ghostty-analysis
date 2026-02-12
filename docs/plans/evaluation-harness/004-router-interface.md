# 004 - Define Router interface + RouteResult schema

- [ ] Done

## Goal
Define a stable routing API (`Router.route(ctx)`) and a structured result schema to support both evaluation and later automation.

## Work
- Define `Router` base protocol/class.
- Define `RouteResult` including:
  - ranked targets (user/team)
  - confidence (High/Med/Low)
  - risk tier (High/Med/Low)
  - evidence-backed explanations (machine-readable)

## Files
Create:
- `packages/inference/src/repo_routing/router/__init__.py`
- `packages/inference/src/repo_routing/router/base.py`
- `packages/inference/src/repo_routing/router/explain.py`

## Acceptance Criteria
- Baselines and learned/heuristic routers can share the same interface.
- Explanations are structured enough to render receipts without hand-wavy language.
