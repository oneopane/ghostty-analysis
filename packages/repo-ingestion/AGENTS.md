# PROJECT KNOWLEDGE BASE

## OVERVIEW
Repository-agnostic history ingestion (GitHub first) with a Typer CLI and a local SQLite explorer.

## STRUCTURE
```
packages/repo-ingestion/
├── main.py                                 # local module entry
├── src/gh_history_ingestion/
│   ├── cli/app.py                           # Typer CLI
│   ├── ingest/                              # backfill, incremental, PR-only flows
│   ├── events/normalizers/                  # issue/PR review/comment normalization
│   ├── github/                              # auth + client helpers
│   ├── providers/github/                    # provider-specific clients
│   ├── storage/                             # db schema + upsert/duckdb
│   └── explorer/                            # local SQLite explorer web app
└── tests/
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| CLI commands | packages/repo-ingestion/src/gh_history_ingestion/cli/app.py | ingest/incremental/pull-requests/explore |
| Backfill ingest | packages/repo-ingestion/src/gh_history_ingestion/ingest/backfill.py | full history pull |
| Incremental ingest | packages/repo-ingestion/src/gh_history_ingestion/ingest/incremental.py | watermark-based updates |
| PR-only backfill | packages/repo-ingestion/src/gh_history_ingestion/ingest/pull_requests.py | optional truth signals |
| Event normalization | packages/repo-ingestion/src/gh_history_ingestion/events/normalizers | issue/PR review/comment types |
| Storage schema | packages/repo-ingestion/src/gh_history_ingestion/storage/schema.py | SQLite tables |
| Explorer app | packages/repo-ingestion/src/gh_history_ingestion/explorer/server.py | local read-only UI |

## CONVENTIONS
- Auth uses GitHub CLI token when available; fallback to `GITHUB_TOKEN`.

## ANTI-PATTERNS (THIS PACKAGE)
- None documented.

## COMMANDS
```bash
uv run --project packages/repo-ingestion repo-ingestion ingest --repo owner/name
uv run --project packages/repo-ingestion repo-ingestion incremental --repo owner/name
uv run --project packages/repo-ingestion repo-ingestion pull-requests --repo owner/name --with-truth
uv run --project packages/repo-ingestion repo-ingestion explore
```

## NOTES
- Explorer defaults to `http://127.0.0.1:8787` and scans `data/github/**` for SQLite files.
