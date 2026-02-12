# PROJECT KNOWLEDGE BASE

## OVERVIEW
Repository-agnostic history ingestion (GitHub first) with a Typer CLI and a local SQLite explorer.

## STRUCTURE
```
packages/ingestion/
├── main.py
├── src/gh_history_ingestion/
│   ├── cli/app.py
│   ├── ingest/
│   ├── events/normalizers/
│   ├── providers/github/
│   ├── storage/
│   └── explorer/
└── tests/
```

## COMMANDS
```bash
uv run --project packages/ingestion ingestion ingest --repo owner/name
uv run --project packages/ingestion ingestion incremental --repo owner/name
uv run --project packages/ingestion ingestion pull-requests --repo owner/name --with-truth
uv run --project packages/ingestion ingestion explore
```
