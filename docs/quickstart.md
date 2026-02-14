# Quickstart (Artifact-Native V2)

## 1) Setup

```bash
uv venv
uv sync
```

## 2) Ingest repository history

```bash
uv run --project packages/cli repo ingestion ingest --repo owner/name
```

## 3) Verify cutoff horizon

```bash
uv run --project packages/cli repo evaluation cutoff \
  --repo owner/name \
  --cutoff 2026-01-01T00:00:00Z
```

## 4) Run an experiment

```bash
uv run --project packages/cli repo experiment run --spec experiments/example.json
```

## 5) Inspect artifact-native outputs

```bash
uv run --project packages/cli repo artifacts list --repo owner/name --run-id <run_id>
uv run --project packages/cli repo artifacts show --repo owner/name --run-id <run_id> --artifact-id <artifact_id>
```

## 6) Plan semantic cache backfill

```bash
uv run --project packages/cli repo backfill semantic \
  --repo owner/name \
  --prompt reviewer_rerank \
  --since 2026-01-01T00:00:00Z \
  --dry-run
```

## 7) Promote a candidate

```bash
uv run --project packages/cli repo experiment candidate add --task-id reviewer_routing --candidate-ref router.llm_rerank@v3
uv run --project packages/cli repo experiment candidate promote --task-id reviewer_routing --candidate-ref router.llm_rerank@v3
```
