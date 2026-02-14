# ghostty-analysis

CLI-first, deterministic experimentation workflows for repository history ingestion, inference/routing, and evaluation.

## Start here

If you want to complete an end-to-end run **without reading source code**:

- **Canonical golden path:** [`docs/examples/e2e-unified-cli.md`](./docs/examples/e2e-unified-cli.md)
- **Artifact strategy memo:** [`docs/examples/README.md`](./docs/examples/README.md)
- **Known-good transcript:** [`docs/examples/artifacts/ghostty-e2e-cli-transcript-v1.md`](./docs/examples/artifacts/ghostty-e2e-cli-transcript-v1.md)
- **Docs index:** [`docs/README.md`](./docs/README.md)

## Workspace packages

- `packages/core`
- `packages/ingestion`
- `packages/inference`
- `packages/experimentation`
- `packages/evaluation`
- `packages/cli`

## CLI entrypoint

```bash
uv run --project packages/cli repo --help
```
