# Unified Experiment CLI + Repo Profile (Implementation Notes)

## Phase 0 Audit Summary

Confirmed:
- Workspace members and package boundaries match the expected monorepo split:
  - `packages/ingestion`
  - `packages/inference`
  - `packages/evaluation`
  - `packages/cli`
- `cli` is the current unified front door and mounts inference/evaluation sub-CLIs.
- Deterministic artifact/data paths are in place:
  - DB: `data/github/<owner>/<repo>/history.sqlite`
  - Eval runs: `data/github/<owner>/<repo>/eval/<run_id>/`
- Strict stale-cutoff leakage guard exists in `evaluation_harness.runner.run_streaming_eval`.
- As-of reads use interval tables via `repo_routing.history.reader.HistoryReader`.

Divergences found during audit:
- Unified experiment UX was incomplete: no first-class `cohort`, `experiment`, `doctor`, or `diff` flow.
- No generalized pinned repo artifact fetch/store utility for per-PR base SHA.
- No per-PR repo-profile IR generation in the evaluation loop.
- Truth coverage ambiguity initially remained; now resolved with explicit truth diagnostics/status in eval outputs.

## Implemented Design Mapping

### Unified CLI
- Added to `cli`:
  - `repo cohort create`
  - `repo experiment init`
  - `repo experiment run`
  - `repo experiment show`
  - `repo experiment list`
  - `repo experiment explain`
  - `repo experiment diff`
  - `repo profile build`
  - `repo doctor`
- Existing `ingestion`, `inference`, and `evaluation` CLI wiring remains intact.

### Cohort + Experiment Artifacts
- Deterministic hashed artifacts:
  - `cohort.json` (`kind=cohort`, `version=v1`, `hash`)
  - `experiment.json` (`kind=experiment_spec`, `version=v1`, `hash`)
- `repo experiment run` behavior:
  - honors `experiment.json.cohort.path/hash` as source-of-truth when locked
  - rejects conflicting inline cohort flags when spec locks cohort
  - uses locked `cohort.pr_cutoffs` and passes them into evaluation runner (no silent recompute)
- `repo experiment run` writes run-local copies:
  - `<run_dir>/cohort.json`
  - `<run_dir>/experiment.json`
  - `<run_dir>/experiment_manifest.json` (records cohort/spec hashes + cutoff source + prefetch provenance)

### Repo Profile IR
- Added `repo_routing.repo_profile` package:
  - `models.py` (identity, manifest, ownership graph, area model, policy signals, vocabulary, QA)
  - `parsers/codeowners.py`
  - `storage.py`
  - `builder.py`
- Added per-PR profile artifact outputs:
  - `<run_dir>/prs/<pr>/repo_profile/profile.json`
  - `<run_dir>/prs/<pr>/repo_profile/qa.json`

### Runner Integration
- Extended `run_streaming_eval(...)` with optional `RepoProfileRunSettings`.
- When enabled:
  - Builds repo profile per PR from pinned artifacts anchored by PR `base_sha`.
  - Writes profile + QA artifacts.
  - Adds repo-profile coverage/QA summary into `per_pr.jsonl`.
  - Supports strict failure mode on missing profile coverage.

### Pinned Artifact Fetcher
- Added `gh_history_ingestion.repo_artifacts.fetcher`:
  - fetch by `base_sha` from GitHub contents API
  - deterministic normalization + SHA256 manifest
  - storage path:
    - `data/github/<owner>/<repo>/repo_artifacts/<base_sha>/...`
    - manifest at `.../manifest.json`
  - per-file provenance includes available source identifiers (`blob_sha`, `source_url`, `git_url`, `download_url`)
- `repo experiment run` and `repo profile build` can prefetch missing pinned artifacts when enabled.
- `repo experiment run` records prefetch provenance in run manifest (`artifact_prefetch.network_used`, fetched files, source metadata, integrity hashes).

## Runbook Snippets

```bash
repo cohort create --repo <owner>/<repo> --from <iso> --end-at <iso> --limit 200 --output cohort.json
repo experiment init --repo <owner>/<repo> --cohort cohort.json --output experiment.json
repo experiment run --repo <owner>/<repo> --cohort cohort.json --spec experiment.json
repo experiment diff --repo <owner>/<repo> --run-a <run_id_a> --run-b <run_id_b>
repo profile build --repo <owner>/<repo> --pr 123 --run-id profile-check
```

Repo profile artifacts live under:
- `data/github/<owner>/<repo>/eval/<run_id>/prs/<pr_number>/repo_profile/`
