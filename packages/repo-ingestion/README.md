
# repo-ingestion

Repository-agnostic repository history ingestion (GitHub first).

## Authentication
Default auth uses the GitHub CLI token when available. It falls back to the
`GITHUB_TOKEN` environment variable.

### GitHub CLI (recommended)
1. `gh auth login`
2. The CLI token is used automatically.

### Environment variable
Set a token manually if you prefer:

```bash
export GITHUB_TOKEN="ghp_..."
```

## Dev Flags
For quick smoke tests, you can limit pages per endpoint:

```bash
repo-ingestion ingest --repo owner/name --db /tmp/repo.db --max-pages 1
```

Or omit `--db` to use the default per-repo location:

```bash
repo-ingestion ingest --repo owner/name
```

Time windows are also supported (RFC3339 timestamps; `--from` is an alias for `--start-at`):

```bash
repo-ingestion ingest --repo owner/name --db /tmp/repo.db \
  --start-at 2024-01-01T00:00:00Z --end-at 2024-02-01T00:00:00Z
```

## Evaluation-ready ingestion (truth signals)

The evaluation harness needs truth signals (requested reviewers/teams, review submitters,
and optionally commenters). Those are populated by the full ingest:

```bash
repo-ingestion ingest --repo owner/name
repo-ingestion incremental --repo owner/name
```

If you only want PRs from a time window, prefer the full ingest with `--start-at/--end-at`.

The `repo-ingestion pull-requests` command is optimized for PR-only backfills. It can be
made evaluation-ready by enabling `--with-truth`, which also fetches issue events,
issue comments, PR reviews, and PR review comments for the PRs in the window:

```bash
repo-ingestion pull-requests --repo owner/name \
  --start-at 2024-01-01T00:00:00Z --end-at 2024-02-01T00:00:00Z \
  --with-truth
```

## Default data location

If you omit `--db`, a stable per-repo database path is used:

`data/github/<owner>/<repo>/history.sqlite`

If only `--start-at` is provided, the run continues until now. If only `--end-at`
is provided, the run includes history up to that time.

## Local SQLite explorer (EDA)

A minimal local web app is included for quick exploratory analysis of ingested
SQLite files under `data/github/...`.

### Run

From the repository root:

```bash
uv run --project packages/repo-ingestion repo-ingestion explore
```

Optional flags:

```bash
uv run --project packages/repo-ingestion repo-ingestion explore \
  --data-root data/github \
  --host 127.0.0.1 \
  --port 8787
```

Then open: `http://127.0.0.1:8787`

### Expected folder structure

The explorer scans recursively for SQLite files under:

`data/github/<owner>/<repo>/...`

Typical default ingestion output:

`data/github/<owner>/<repo>/history.sqlite`

### Features

- Database discovery grouped by owner/repo
- Table list with row counts
- Schema viewer (name, type, nullability, PK, default)
- Paginated row browsing (100 rows/page default)
- Sorting by a chosen column
- Global text contains filter across all columns
- Read-only SQL scratchpad (`SELECT` / `WITH ... SELECT` only)

### Known limitations

- Row counts and filtered totals use `COUNT(*)`, which can be slow on very large tables.
- Global filter is simple `LIKE` matching and may be slow on wide tables.
- SQL scratchpad supports a single statement and is intentionally read-only.
- This tool is local/dev-only (no auth, no multi-user isolation).
