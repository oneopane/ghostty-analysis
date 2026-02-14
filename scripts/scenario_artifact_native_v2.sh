#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <owner/name> [since_iso]"
  exit 2
fi

REPO="$1"
SINCE="${2:-2026-01-01T00:00:00Z}"
RUN_ID="scenario-v2"

uv run --project packages/cli repo ingestion ingest --repo "$REPO"

uv run --project packages/cli repo evaluation cutoff \
  --repo "$REPO" \
  --cutoff "$SINCE" || true

# Run a minimal evaluation via experiment spec path if available in local setup.
# Replace with a real spec in your environment.
# uv run --project packages/cli repo experiment run --spec experiments/example.json

uv run --project packages/cli repo artifacts list \
  --repo "$REPO" \
  --run-id "$RUN_ID" || true

uv run --project packages/cli repo backfill semantic \
  --repo "$REPO" \
  --prompt reviewer_rerank \
  --since "$SINCE" \
  --dry-run

echo "scenario complete"
