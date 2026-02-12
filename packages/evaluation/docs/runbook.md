# Evaluation Runbook

This runbook explains how to run offline routing evaluations and inspect outputs.

## 1) Prerequisites

From repo root:

```bash
uv venv
uv sync
```

Ensure ingestion data exists:

```bash
uv run --project packages/ingestion ingestion ingest --repo <owner>/<repo>
```

If using PR-window ingestion, include truth signals:

```bash
uv run --project packages/ingestion ingestion pull-requests \
  --repo <owner>/<repo> --start-at <iso> --end-at <iso> --with-truth
```

Expected DB:

`data/github/<owner>/<repo>/history.sqlite`

## 2) Pick PRs to evaluate

Option A: explicit PRs

```bash
uv run --project packages/evaluation evaluation run \
  --repo <owner>/<repo> \
  --pr 101 --pr 102 \
  --router mentions --router popularity
```

Option B: sample by created_at window

```bash
uv run --project packages/evaluation evaluation run \
  --repo <owner>/<repo> \
  --from 2024-01-01T00:00:00Z --end-at 2024-02-01T00:00:00Z \
  --limit 50 \
  --router mentions
```

## 3) Run with import-path router (optional)

```bash
uv run --project packages/evaluation evaluation run \
  --repo <owner>/<repo> \
  --pr 101 \
  --router-import repo_routing.examples.llm_router_example:create_router \
  --router-config path/to/router-config.json
```

## 4) Inspect run outputs

List runs:

```bash
uv run --project packages/evaluation evaluation list --repo <owner>/<repo>
```

Show report:

```bash
uv run --project packages/evaluation evaluation show \
  --repo <owner>/<repo> --run-id <run_id>
```

Explain one PR/router:

```bash
uv run --project packages/evaluation evaluation explain \
  --repo <owner>/<repo> --run-id <run_id> --pr 101 --router mentions
```

## 5) Output layout

Run root:

`data/github/<owner>/<repo>/eval/<run_id>/`

Key files:

- `manifest.json`
- `report.json`
- `report.md`
- `per_pr.jsonl`
- `prs/<pr>/snapshot.json`
- `prs/<pr>/inputs.json`
- `prs/<pr>/routes/<router_id>.json`
- optional `prs/<pr>/features/<router_id>.json`

## 6) Guardrails and failure modes

- `strict_streaming_eval=true` (default) aborts if any PR cutoff is after
  `db_max_event_occurred_at`.
- Truth excludes bots and PR author by default.
- Default truth policy is `first_response_v1`, using configured `truth_window`
  (default 60 minutes) and scanning `review_submitted` + `review_comment`.
- Missing router configs (for `stewards`) fail fast.

## 7) Recommended experiment loop

1. Run a baseline set (`mentions`, `popularity`, `codeowners`).
2. Run candidate experimental router(s) on same PR cohort.
3. Compare `report.json` routing metrics and queue slices.
4. Spot-check `explain` output for qualitative failure modes.
5. Capture run-id + config in experiment notes.
