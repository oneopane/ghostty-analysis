# Codebase Map Explorer (Local Web UI)

This repository ships a local-only web UI built on MkDocs Material plus an in-browser Explorer page.

## Install

Prereqs:

- Python + `uv` installed

Optional (recommended for working on the repo generally):

```bash
uv sync
```

## Run (Dev Server)

One command:

```bash
uv run python scripts/docs_serve.py
```

Then open:

- http://127.0.0.1:8000/

## Pages To Open

- Explorer: `/explorer/`
- Codebase Map Pack:
  - `/codebase_map_pack/architecture/`
  - `/codebase_map_pack/data_lineage/`
  - `/codebase_map_pack/pipelines/`

## Runtime Constraints (No CDN)

- Mermaid and Cytoscape are vendored under `docs/assets/vendor/`.
- The Explorer loads JSON from `docs/_artifacts/` at runtime.

## Updating / Regenerating Maps

- Update Markdown in `docs/codebase_map_pack/`.
- Update JSON in `docs/_artifacts/`.
- Re-stamp `ref` deep links into JSON (optional but recommended):

```bash
python3 scripts/build_codebase_map_refs.py
```
