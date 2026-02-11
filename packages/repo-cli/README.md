# repo-cli

One CLI that wires together:

- `repo-ingestion` (build the per-repo history database)
- `repo-routing` (generate routing artifacts)
- `evaluation-harness` (compute lightweight evaluation metrics)

Run:

`repo --help`

Unified experiment workflow:

```bash
repo cohort create --repo <owner>/<repo> --from <iso> --end-at <iso> --limit 200 --output cohort.json
repo experiment init --repo <owner>/<repo> --cohort cohort.json --output experiment.json
repo experiment run --repo <owner>/<repo> --cohort cohort.json --spec experiment.json
repo experiment diff --repo <owner>/<repo> --run-a <run_id_a> --run-b <run_id_b>
repo profile build --repo <owner>/<repo> --pr 123 --run-id profile-check
repo doctor --repo <owner>/<repo> --cohort cohort.json
```

Notes:
- If `experiment.json` locks `cohort.path` / `cohort.hash`, `repo experiment run` uses that cohort as source-of-truth and rejects conflicting inline cohort flags.
- Eval execution uses locked `cohort.pr_cutoffs` and passes those exact cutoffs into the runner (no silent recompute).
- Run provenance is written to `<run_dir>/experiment_manifest.json`, including `cutoff_source`, `pr_cutoffs`, and `artifact_prefetch` network activity details.
