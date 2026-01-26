# repo-routing

Post-ingest routing artifacts and heuristics.

This package is intentionally separate from `repo-ingestion`:

- `repo-ingestion` builds the canonical history database.
- `repo-routing` reads that database and generates artifacts used for routing and evaluation.

Default per-repo DB location is:

`data/github/<owner>/<repo>/history.sqlite`

This package does not call GitHub APIs. It only reads local history databases.

Use via the unified CLI:

`repo routing --help`
