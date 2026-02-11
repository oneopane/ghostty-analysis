# Examples: Artifact Strategy for CLI-First Experimentation

This memo defines the **minimal-but-complete artifact set** for a data scientist to run end-to-end experiments in this repository **without reading source code**.

## Start here

- Canonical walkthrough: [`e2e-unified-cli.md`](./e2e-unified-cli.md)

## Objective

Provide one clear golden path while keeping enough references for deeper troubleshooting and interpretation.

## Minimal artifact set (user-facing)

| Artifact | Why it exists | Required for golden path |
|---|---|---|
| `docs/examples/e2e-unified-cli.md` | Single canonical runbook (ingest → cohort/spec → run → inspect → diff → quality checks) | Yes |
| `packages/cli/README.md` | Quick command surface map for `repo` CLI | Yes |
| `cohort.json` | Locked PR set + cutoff context + hash | Yes |
| `experiment.json` | Locked experiment settings + router definitions + hash | Yes |
| `data/github/<owner>/<repo>/eval/<run_id>/manifest.json` | Effective evaluation config + provenance | Yes |
| `data/github/<owner>/<repo>/eval/<run_id>/report.json` | Machine-readable metrics summary | Yes |
| `data/github/<owner>/<repo>/eval/<run_id>/report.md` | Human-readable run summary | Yes |
| `data/github/<owner>/<repo>/eval/<run_id>/per_pr.jsonl` | Per-PR evidence, truth status, router outputs | Yes |
| `data/github/<owner>/<repo>/eval/<run_id>/experiment_manifest.json` | Cohort/spec hash lock + orchestration metadata | Yes |

## Versioned supporting artifacts

These are useful for onboarding and reproducibility, but not strictly required to run the lifecycle:

- `docs/examples/artifacts/ghostty-e2e-cli-transcript-v1.md` (known-good command/output transcript)
- `scripts/print_cohort_pr.py` (tiny helper to pick PR numbers from `cohort.json`)

## What to include vs exclude

### Include

- Copy-paste commands that run from repository root.
- `ghostty-org/ghostty` concrete examples.
- Expected output files after each stage.
- Success signals and common failure fixes.
- Links to deeper docs, without requiring source-code navigation.

### Exclude (from golden path)

- Implementation details of internal Python modules.
- Historical planning docs as required reading.
- Notebook-only paths as required steps.
- Optional router internals or feature engineering mechanics.

Those remain valuable references, but not part of the first-run path.

## Tradeoffs

### Too many artifacts/docs

- Increases cognitive load.
- New users spend time comparing overlapping guides.
- Higher risk of stale instructions.

### Too little guidance

- Users can run commands but cannot tell whether outputs are correct.
- Missing context leads to misinterpretation of `report.json` and `per_pr.jsonl`.
- Troubleshooting falls back to source-code reading.

### Chosen balance

- One canonical doc for complete lifecycle.
- Small set of mandatory artifacts with explicit success criteria.
- Deep-dive links for optional expansion.

## Maintenance policy

When CLI flags or command names change:

1. Update `docs/examples/e2e-unified-cli.md` first.
2. Update package README pointers (`packages/*/README.md`).
3. Run naming checks before merge:
   - `uv run python scripts/validate_docs_naming.py`
4. Keep CI docs checks green (`.github/workflows/docs-checks.yml`).
