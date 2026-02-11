# Known-Good Transcript v1: Ghostty Unified CLI E2E

Status: reference transcript for the golden path in [`../e2e-unified-cli.md`](../e2e-unified-cli.md).

Version: `v1`

Scope:

- CLI-first lifecycle on `ghostty-org/ghostty`
- ingest → doctor → cohort/spec → run → inspect → diff → evaluation check

Notes:

- Output is intentionally compact (key lines only).
- Run IDs are examples; your local run IDs will differ.
- Use this transcript to sanity-check flow, not to assert byte-identical CLI stdout.

---

## 0) Verify command surface

```bash
$ uv run --project packages/cli repo --help
```

Expected command groups include:

- `ingest`, `incremental`, `pull-requests`
- `doctor`, `cohort`, `experiment`, `profile`
- `inference`, `evaluation`

---

## 1) Ingest

```bash
$ uv run --project packages/cli repo pull-requests \
    --repo ghostty-org/ghostty \
    --data-dir data \
    --start-at 2025-08-01T00:00:00Z \
    --end-at 2026-02-01T00:00:00Z \
    --with-truth
```

Success signal:

- exits 0
- `data/github/ghostty-org/ghostty/history.sqlite` exists

---

## 2) Doctor check

```bash
$ uv run --project packages/cli repo doctor \
    --repo ghostty-org/ghostty \
    --data-dir data \
    --start-at 2025-08-01T00:00:00Z \
    --end-at 2026-02-01T00:00:00Z \
    --limit 200
```

Expected:

- readiness summary printed
- no blocking stale-cutoff errors for planned window

---

## 3) Create cohort and specs

```bash
$ uv run --project packages/cli repo cohort create \
    --repo ghostty-org/ghostty \
    --data-dir data \
    --start-at 2025-08-01T00:00:00Z \
    --end-at 2026-02-01T00:00:00Z \
    --limit 200 \
    --seed 4242 \
    --output artifacts/examples/ghostty-e2e/cohort.v1.json
```

```bash
$ uv run --project packages/cli repo experiment init \
    --repo ghostty-org/ghostty \
    --cohort artifacts/examples/ghostty-e2e/cohort.v1.json \
    --router mentions --router popularity --router codeowners \
    --profile audit \
    --output artifacts/examples/ghostty-e2e/experiment.baseline.json
```

```bash
$ uv run --project packages/cli repo experiment init \
    --repo ghostty-org/ghostty \
    --cohort artifacts/examples/ghostty-e2e/cohort.v1.json \
    --router mentions --router popularity --router codeowners --router union --router hybrid_ranker \
    --profile audit \
    --output artifacts/examples/ghostty-e2e/experiment.hybrid.json
```

Expected files:

- `artifacts/examples/ghostty-e2e/cohort.v1.json`
- `artifacts/examples/ghostty-e2e/experiment.baseline.json`
- `artifacts/examples/ghostty-e2e/experiment.hybrid.json`

---

## 4) Run baseline and hybrid specs

```bash
$ uv run --project packages/cli repo experiment run \
    --spec artifacts/examples/ghostty-e2e/experiment.baseline.json \
    --data-dir data \
    --run-id ghostty-baseline-20260211T221500Z
```

```bash
$ uv run --project packages/cli repo experiment run \
    --spec artifacts/examples/ghostty-e2e/experiment.hybrid.json \
    --data-dir data \
    --run-id ghostty-hybrid-20260211T221900Z
```

Expected run outputs under each run dir:

- `cohort.json`
- `experiment.json`
- `experiment_manifest.json`
- `manifest.json`
- `report.json`
- `report.md`
- `per_pr.jsonl`

---

## 5) Inspect and diff

```bash
$ uv run --project packages/cli repo experiment show \
    --repo ghostty-org/ghostty \
    --run-id ghostty-baseline-20260211T221500Z \
    --data-dir data
```

```bash
$ uv run --project packages/cli repo experiment show \
    --repo ghostty-org/ghostty \
    --run-id ghostty-hybrid-20260211T221900Z \
    --data-dir data
```

```bash
$ uv run --project packages/cli repo experiment diff \
    --repo ghostty-org/ghostty \
    --run-a ghostty-baseline-20260211T221500Z \
    --run-b ghostty-hybrid-20260211T221900Z \
    --data-dir data
```

Expected:

- metric deltas printed
- no cohort mismatch failure (if both runs share cohort hash)

---

## 6) Evaluation and strict check

```bash
$ uv run --project packages/cli repo evaluation show \
    --repo ghostty-org/ghostty \
    --run-id ghostty-hybrid-20260211T221900Z \
    --data-dir data
```

```bash
$ uv run --project packages/cli repo doctor \
    --repo ghostty-org/ghostty \
    --cohort artifacts/examples/ghostty-e2e/cohort.v1.json \
    --data-dir data \
    --strict
```

Expected:

- evaluation summary renders
- strict doctor passes or reports explicit actionable failures

---

## Reference real artifact tree

A real prior audit run exists at:

- `../../data/github/ghostty-org/ghostty/eval/audit-ghostty-20260210-6mo-s4242-r3-v3/`

Use it as a concrete file-layout example for downstream analysis tooling.
