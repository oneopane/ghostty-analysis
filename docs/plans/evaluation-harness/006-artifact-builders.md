# 006 - Implement routing artifact builders (optional v0)

- [ ] Done

## Goal
Generate reusable artifacts (e.g. area map, reviewer stats) to speed routing and evaluation runs.

## Work
- `area_map` builder: derive top-level directories + optional overrides into a stable mapping.
- `reviewer_stats` builder: compute decayed reviewer statistics as-of a watermark (for reproducibility).
- Write a `manifest.json` describing inputs, versions, and watermarks.

## Files
Create:
- `packages/inference/src/repo_routing/artifacts/__init__.py`
- `packages/inference/src/repo_routing/artifacts/area_map.py`
- `packages/inference/src/repo_routing/artifacts/reviewer_stats.py`
- `packages/inference/src/repo_routing/artifacts/manifest.py`

## Acceptance Criteria
- Artifacts are deterministic given the same DB watermark + config.
- Artifacts are stored under `data/github/<owner>/<repo>/artifacts/routing/`.
