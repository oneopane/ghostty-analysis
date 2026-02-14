# Start Here

This repo includes a local docs site + interactive “Codebase Map Explorer” for the map pack under `docs/codebase_map_pack/` and JSON artifacts under `docs/_artifacts/`.

- Explorer UI: `explorer.md`
- Architecture: `codebase_map_pack/architecture.md`
- Data Lineage: `codebase_map_pack/data_lineage.md`
- Pipelines: `codebase_map_pack/pipelines.md`

Run locally:

```bash
uv run python scripts/docs_serve.py
```

Then open http://127.0.0.1:8000/ and visit the Explorer at `/explorer/`.

More details: `explorer_setup.md`.

# Documentation Index

## Start here (new users)

If you want one end-to-end workflow without reading source code:

- **Quickstart (artifact-native V2):** [`quickstart.md`](./quickstart.md)
- **Artifact/cache key reference:** [`artifact-types-cache-keys.md`](./artifact-types-cache-keys.md)
- **Canonical golden path:** [`examples/e2e-unified-cli.md`](./examples/e2e-unified-cli.md)
- **Artifact strategy memo:** [`examples/README.md`](./examples/README.md)
- **Known-good transcript:** [`examples/artifacts/ghostty-e2e-cli-transcript-v1.md`](./examples/artifacts/ghostty-e2e-cli-transcript-v1.md)

## Core guides

- Repository architecture + extension map: [`codebase-experimentation-guide.md`](./codebase-experimentation-guide.md)
- Architecture brief (state + risks): [`architecture-brief.md`](./architecture-brief.md)

## Codebase Map Explorer

- Map Pack docs: [`codebase_map_pack/index.md`](./codebase_map_pack/index.md)
- Local Explorer UI instructions: [`explorer_setup.md`](./explorer_setup.md)

## Domain-specific docs

- Attention routing docs: [`attention-routing/README.md`](./attention-routing/README.md)
- Evaluation implementation plan tasks: [`plans/evaluation-harness/README.md`](./plans/evaluation-harness/README.md)

## Package-local docs

- CLI entrypoint: `../packages/cli/README.md`
- Core shared primitives: `../packages/core/README.md`
- Ingestion: `../packages/ingestion/README.md`
- Inference: `../packages/inference/README.md`
- Experimentation: `../packages/experimentation/README.md`
- Evaluation: `../packages/evaluation/README.md`
