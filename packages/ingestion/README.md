# ingestion

## Start here

If you want the complete unified workflow (not just ingestion commands), use:

- `../../docs/examples/e2e-unified-cli.md`

Repository-agnostic repository history ingestion (GitHub first).

## Authentication
Default auth uses the GitHub CLI token when available. It falls back to the
`GITHUB_TOKEN` environment variable.

### GitHub CLI (recommended)
1. `gh auth login`
2. The CLI token is used automatically.

### Environment variable
```bash
export GITHUB_TOKEN="ghp_..."
```

## Common usage

```bash
ingestion ingest --repo owner/name
ingestion incremental --repo owner/name
```

PR-window ingest with truth signals:

```bash
ingestion pull-requests --repo owner/name \
  --start-at 2024-01-01T00:00:00Z --end-at 2024-02-01T00:00:00Z \
  --with-truth
```

Default DB path when `--db` is omitted:

`data/github/<owner>/<repo>/history.sqlite`

## Local SQLite explorer

```bash
uv run --project packages/ingestion ingestion explore
```
