# Golden Path: End-to-End Experimentation via Unified CLI (`repo`)

Audience: data scientists and experimenters who want a **no-source-code** workflow.

Use case: run the complete lifecycle for `ghostty-org/ghostty`:

1. ingest history,
2. check data readiness,
3. lock a cohort,
4. lock experiment specs,
5. run experiments,
6. inspect outputs,
7. compare runs,
8. run evaluation/quality checks.

---

## Assumptions

- You run commands from repository root.
- You use `uv` and have network access for ingestion.
- GitHub auth is configured (`gh auth login`) or `GITHUB_TOKEN` is set.
- Default data layout is used: `data/github/<owner>/<repo>/...`.
- You are using current command naming (`repo inference`, `repo evaluation`).

---

## Compact copy/paste quickstart

```bash
# 0) setup
uv venv
uv sync

export REPO="ghostty-org/ghostty"
export DATA_DIR="data"
export START_AT="2025-08-01T00:00:00Z"
export END_AT="2026-02-01T00:00:00Z"
export OUT_DIR="artifacts/examples/ghostty-e2e"
mkdir -p "$OUT_DIR"

# 1) ingest (fast windowed path)
uv run --project packages/cli repo pull-requests \
  --repo "$REPO" \
  --data-dir "$DATA_DIR" \
  --start-at "$START_AT" \
  --end-at "$END_AT" \
  --with-truth

# 2) readiness checks
uv run --project packages/cli repo doctor \
  --repo "$REPO" \
  --data-dir "$DATA_DIR" \
  --start-at "$START_AT" \
  --end-at "$END_AT" \
  --limit 200

# 3) lock cohort + specs
uv run --project packages/cli repo cohort create \
  --repo "$REPO" \
  --data-dir "$DATA_DIR" \
  --start-at "$START_AT" \
  --end-at "$END_AT" \
  --limit 200 \
  --seed 4242 \
  --output "$OUT_DIR/cohort.v1.json"

uv run --project packages/cli repo experiment init \
  --repo "$REPO" \
  --cohort "$OUT_DIR/cohort.v1.json" \
  --router mentions \
  --router popularity \
  --router codeowners \
  --profile audit \
  --output "$OUT_DIR/experiment.baseline.json"

uv run --project packages/cli repo experiment init \
  --repo "$REPO" \
  --cohort "$OUT_DIR/cohort.v1.json" \
  --router mentions \
  --router popularity \
  --router codeowners \
  --router union \
  --router hybrid_ranker \
  --profile audit \
  --output "$OUT_DIR/experiment.hybrid.json"

# 4) run two experiments for comparison
export RUN_A="ghostty-baseline-$(date -u +%Y%m%dT%H%M%SZ)"
export RUN_B="ghostty-hybrid-$(date -u +%Y%m%dT%H%M%SZ)"

uv run --project packages/cli repo experiment run \
  --spec "$OUT_DIR/experiment.baseline.json" \
  --data-dir "$DATA_DIR" \
  --run-id "$RUN_A"

uv run --project packages/cli repo experiment run \
  --spec "$OUT_DIR/experiment.hybrid.json" \
  --data-dir "$DATA_DIR" \
  --run-id "$RUN_B"

# 5) inspect + diff
uv run --project packages/cli repo experiment show --repo "$REPO" --run-id "$RUN_A" --data-dir "$DATA_DIR"
uv run --project packages/cli repo experiment show --repo "$REPO" --run-id "$RUN_B" --data-dir "$DATA_DIR"
uv run --project packages/cli repo experiment diff --repo "$REPO" --run-a "$RUN_A" --run-b "$RUN_B" --data-dir "$DATA_DIR"

# 6) direct evaluation surface + strict quality check
uv run --project packages/cli repo evaluation show --repo "$REPO" --run-id "$RUN_B" --data-dir "$DATA_DIR"
uv run --project packages/cli repo doctor --repo "$REPO" --cohort "$OUT_DIR/cohort.v1.json" --data-dir "$DATA_DIR" --strict
```

If you want a compact reference transcript with expected outputs, see:

- [`artifacts/ghostty-e2e-cli-transcript-v1.md`](./artifacts/ghostty-e2e-cli-transcript-v1.md)

---

## Full golden path (with expected artifacts)

## 1) Environment and auth

```bash
gh auth login
uv venv
uv sync
uv run --project packages/cli repo --help
```

Success signal:

- `repo --help` lists: `ingest`, `incremental`, `pull-requests`, `doctor`, `cohort`, `experiment`, `profile`, `inference`, `evaluation`.

---

## 2) Ingest repository history

You have two supported ingestion profiles:

### Profile A (fast, windowed)

Use this for first pass validation and rapid iteration.

```bash
uv run --project packages/cli repo pull-requests \
  --repo "$REPO" \
  --data-dir "$DATA_DIR" \
  --start-at "$START_AT" \
  --end-at "$END_AT" \
  --with-truth
```

### Profile B (thorough, recommended for final comparisons)

Use this before publishing conclusions.

```bash
uv run --project packages/cli repo ingest --repo "$REPO" --data-dir "$DATA_DIR"
uv run --project packages/cli repo incremental --repo "$REPO" --data-dir "$DATA_DIR"
```

Expected artifact:

- `data/github/ghostty-org/ghostty/history.sqlite`

Success signals:

- command exits 0,
- SQLite DB exists at the path above.

---

## 3) Data readiness / quality preflight

```bash
uv run --project packages/cli repo doctor \
  --repo "$REPO" \
  --data-dir "$DATA_DIR" \
  --start-at "$START_AT" \
  --end-at "$END_AT" \
  --limit 200
```

Optional strict gate:

```bash
uv run --project packages/cli repo doctor \
  --repo "$REPO" \
  --data-dir "$DATA_DIR" \
  --start-at "$START_AT" \
  --end-at "$END_AT" \
  --limit 200 \
  --strict
```

Success signals:

- no stale-cutoff blocking diagnostics,
- acceptable profile/artifact coverage for your experiment mode.

---

## 4) Lock cohort and experiment specs

### 4.1 Create deterministic cohort

```bash
uv run --project packages/cli repo cohort create \
  --repo "$REPO" \
  --data-dir "$DATA_DIR" \
  --start-at "$START_AT" \
  --end-at "$END_AT" \
  --limit 200 \
  --seed 4242 \
  --output "$OUT_DIR/cohort.v1.json"
```

Expected artifact:

- `$OUT_DIR/cohort.v1.json`

Key fields to verify in that JSON:

- `kind = "cohort"`
- `version = "v1"`
- non-empty `pr_numbers`
- `pr_cutoffs`
- `hash`

### 4.2 Create two specs for A/B comparison

Baseline spec:

```bash
uv run --project packages/cli repo experiment init \
  --repo "$REPO" \
  --cohort "$OUT_DIR/cohort.v1.json" \
  --router mentions \
  --router popularity \
  --router codeowners \
  --profile audit \
  --output "$OUT_DIR/experiment.baseline.json"
```

Hybrid candidate spec:

```bash
uv run --project packages/cli repo experiment init \
  --repo "$REPO" \
  --cohort "$OUT_DIR/cohort.v1.json" \
  --router mentions \
  --router popularity \
  --router codeowners \
  --router union \
  --router hybrid_ranker \
  --profile audit \
  --output "$OUT_DIR/experiment.hybrid.json"
```

Expected artifacts:

- `$OUT_DIR/experiment.baseline.json`
- `$OUT_DIR/experiment.hybrid.json`

Key fields to verify:

- `kind = "experiment_spec"`
- `version = "v1"`
- `cohort` lock info
- router list
- `hash`

---

## 5) Run experiments

```bash
export RUN_A="ghostty-baseline-$(date -u +%Y%m%dT%H%M%SZ)"
export RUN_B="ghostty-hybrid-$(date -u +%Y%m%dT%H%M%SZ)"

uv run --project packages/cli repo experiment run \
  --spec "$OUT_DIR/experiment.baseline.json" \
  --data-dir "$DATA_DIR" \
  --run-id "$RUN_A"

uv run --project packages/cli repo experiment run \
  --spec "$OUT_DIR/experiment.hybrid.json" \
  --data-dir "$DATA_DIR" \
  --run-id "$RUN_B"
```

Expected run directories:

- `data/github/ghostty-org/ghostty/eval/$RUN_A/`
- `data/github/ghostty-org/ghostty/eval/$RUN_B/`

Expected files in each run dir:

- `cohort.json`
- `experiment.json`
- `experiment_manifest.json`
- `manifest.json`
- `report.json`
- `report.md`
- `per_pr.jsonl`
- `prs/<pr_number>/...` (per-PR artifacts)

---

## 6) Inspect outputs

```bash
uv run --project packages/cli repo experiment list --repo "$REPO" --data-dir "$DATA_DIR"
uv run --project packages/cli repo experiment show --repo "$REPO" --run-id "$RUN_A" --data-dir "$DATA_DIR"
uv run --project packages/cli repo experiment show --repo "$REPO" --run-id "$RUN_B" --data-dir "$DATA_DIR"
```

To inspect one PR explanation, pick a PR from the cohort:

```bash
python3 scripts/print_cohort_pr.py "$OUT_DIR/cohort.v1.json"
# optional: list all PRs
python3 scripts/print_cohort_pr.py "$OUT_DIR/cohort.v1.json" --all
```

Then run:

```bash
# replace <PR_NUMBER> with one value from cohort pr_numbers
uv run --project packages/cli repo experiment explain \
  --repo "$REPO" \
  --run-id "$RUN_B" \
  --pr <PR_NUMBER> \
  --router hybrid_ranker \
  --data-dir "$DATA_DIR"
```

---

## 7) Compare runs

```bash
uv run --project packages/cli repo experiment diff \
  --repo "$REPO" \
  --run-a "$RUN_A" \
  --run-b "$RUN_B" \
  --data-dir "$DATA_DIR"
```

Success signal:

- command exits 0 and prints metric deltas.

Note:

- `diff` enforces cohort-hash compatibility by default.
- Use `--force` only when intentionally comparing non-equivalent cohorts.

---

## 8) Evaluation and quality checks

`repo experiment run` already produces evaluation outputs. Use these to validate quality:

```bash
uv run --project packages/cli repo evaluation show --repo "$REPO" --run-id "$RUN_B" --data-dir "$DATA_DIR"
```

Strict post-run readiness check:

```bash
uv run --project packages/cli repo doctor \
  --repo "$REPO" \
  --cohort "$OUT_DIR/cohort.v1.json" \
  --data-dir "$DATA_DIR" \
  --strict
```

Optional standalone repo-profile check for one PR:

```bash
# replace <PR_NUMBER> with a PR from the cohort
uv run --project packages/cli repo profile build \
  --repo "$REPO" \
  --data-dir "$DATA_DIR" \
  --run-id "$RUN_B" \
  --pr <PR_NUMBER> \
  --strict
```

Optional full validation script:

```bash
./scripts/validate_feature_stack.sh
```

---

## Expected artifact map (reference)

```text
artifacts/examples/ghostty-e2e/
  cohort.v1.json
  experiment.baseline.json
  experiment.hybrid.json

data/github/ghostty-org/ghostty/
  history.sqlite
  eval/
    <run_id>/
      cohort.json
      experiment.json
      experiment_manifest.json
      manifest.json
      report.json
      report.md
      per_pr.jsonl
      prs/
        <pr_number>/
          repo_profile/
            profile.json
            qa.json
```

---

## Success signals checklist

You have completed the lifecycle when all are true:

- [ ] `history.sqlite` exists for `ghostty-org/ghostty`.
- [ ] `repo doctor` reports acceptable readiness for your cohort.
- [ ] cohort/spec artifacts are created with hashes.
- [ ] at least one run dir exists with `report.json`, `report.md`, `per_pr.jsonl`, `manifest.json`, `experiment_manifest.json`.
- [ ] `repo experiment show` works for each run.
- [ ] `repo experiment diff` works between runs.
- [ ] strict doctor check passes (or you documented why it does not).

---

## Common failure modes + quick fixes

### 1) Auth or rate-limit errors during ingestion

Symptoms:

- GitHub API failures, unauthorized, low-rate-limit behavior.

Fix:

- Run `gh auth login`, or export `GITHUB_TOKEN`.

### 2) No PRs selected in cohort

Symptoms:

- empty `pr_numbers`.

Fix:

- widen `--start-at`/`--end-at`, remove/reduce `--limit`, verify DB freshness.

### 3) Stale-cutoff readiness failures

Symptoms:

- doctor warns/fails on stale cutoffs.

Fix:

- run `repo incremental`, or rerun ingestion over the needed time window.

### 4) Repo profile strict coverage failures

Symptoms:

- strict run/doctor fails due to missing pinned artifacts.

Fix:

- ingest missing data,
- or allow one-time prefetch in controlled runs (`--allow-fetch-missing-artifacts` in experiment/profile flows).

### 5) Cohort mismatch on diff

Symptoms:

- `cohort hash mismatch`.

Fix:

- compare runs produced from the same cohort artifact, or pass `--force` only intentionally.

---

## Deep-dive references (no source-code reading required)

- Artifact strategy memo: [`README.md`](./README.md)
- Full architecture + extension guide: [`../codebase-experimentation-guide.md`](../codebase-experimentation-guide.md)
- CLI package entrypoint: [`../../packages/cli/README.md`](../../packages/cli/README.md)
- Evaluation docs:
  - `../../packages/evaluation/docs/runbook.md`
  - `../../packages/evaluation/docs/metrics.md`
  - `../../packages/evaluation/docs/baselines.md`
- Known-good transcript snapshot:
  - [`artifacts/ghostty-e2e-cli-transcript-v1.md`](./artifacts/ghostty-e2e-cli-transcript-v1.md)
- Existing real run artifacts (example):
  - `../../data/github/ghostty-org/ghostty/eval/audit-ghostty-20260210-6mo-s4242-r3-v3/`
- Optional helper script for selecting PRs from cohort:
  - `../../scripts/print_cohort_pr.py`

Optional contract-level references:

- `../../packages/cli/tests/test_unified_experiment_cli.py`
- `../../packages/evaluation/tests/test_end_to_end_run.py`
