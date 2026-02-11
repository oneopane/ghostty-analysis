# cli

## Start here

For a full end-to-end, no-code walkthrough (ingest → cohort/spec → run → inspect → diff → quality checks):

- `../../docs/examples/e2e-unified-cli.md`

Artifact strategy + what to keep as source-of-truth artifacts:

- `../../docs/examples/README.md`

Unified `repo` command surface wiring together:

- `ingestion` (history database creation/updates)
- `inference` (routing/inference artifact tooling)
- `experimentation` (cohort/spec workflows, quality gates, profile/doctor)
- `evaluation` (offline scoring/reporting)

Run:

`repo --help`

Unified experiment workflow:

```bash
repo cohort create --repo <owner>/<repo> --from <iso> --end-at <iso> --limit 200 --output cohort.json
repo experiment init --repo <owner>/<repo> --cohort cohort.json --output experiment.json
repo experiment run --spec experiment.json --data-dir data
repo experiment diff --repo <owner>/<repo> --run-a <run_id_a> --run-b <run_id_b>
repo profile build --repo <owner>/<repo> --pr 123 --run-id profile-check
repo doctor --repo <owner>/<repo> --cohort cohort.json
```
