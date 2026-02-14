# Labels & Metrics

This repo separates:

- Truth policies and coverage-aware truth extraction (`evaluation_harness.truth*`).
- Routing metrics computed from router outputs vs truth targets (`evaluation_harness.metrics.*`).
- Additional diagnostics and slices emitted to `report.json`.

## Labels (Truth) {#labels}

### Behavior Truth (first eligible post-cutoff action)

- Implementation: `packages/evaluation/src/evaluation_harness/truth.py`
- Policy registry + plugin support: `packages/evaluation/src/evaluation_harness/truth_policy.py`

Built-in truth policy ids (from `builtin_truth_policy_specs()`):

- `first_response_v1` (sources: reviews + review_comments)
- `first_approval_v1` (sources: reviews; state filter `APPROVED`)
- `merger_v1` (sources: events; currently returns `policy_unavailable` via readiness gate in `truth_with_policy`)
- `hybrid_owner_v1` (sources: reviews + events + review_requests; currently returns `policy_unavailable` via readiness gate in `truth_with_policy`)

Truth output shape:

- Per PR, evaluation emits `truth` into `per_pr.jsonl` with:
  - `primary_policy`
  - `policies[policy_id].targets` (list of selected logins; empty if none)
  - `policies[policy_id].status` (see `TruthStatus`)
  - `policies[policy_id].diagnostics`

Truth status values (coverage-aware):

- `observed`
- `no_post_cutoff_response`
- `unknown_due_to_ingestion_gap`
- `policy_unavailable`

### Intent Truth (review requests near cutoff)

- Implementation: `packages/evaluation/src/evaluation_harness/truth.py` (`intent_truth_from_review_requests`)
- Reads as-of review request intervals: `pull_request_review_request_intervals` joined to `events`.

## Metrics {#metrics}

Metric implementations:

- Routing agreement: `packages/evaluation/src/evaluation_harness/metrics/routing_agreement.py`
- Gate correlation: `packages/evaluation/src/evaluation_harness/metrics/gates.py`
- Queue metrics: `packages/evaluation/src/evaluation_harness/metrics/queue.py`

### Routing Agreement (ranking)

Per PR:

- `hit_at_1`, `hit_at_3`, `hit_at_5`, `mrr`

Aggregated (mean across PRs):

- `RoutingAgreementSummary`

### Gate Correlation (classification-style correlation)

Per PR:

- `merged`, `missing_issue`, `missing_ai_disclosure`, `missing_provenance`

Aggregated:

- Missing rates and merged-rate deltas for missing vs present per gate field.

### Queue Metrics (time-to-event)

Per PR:

- `ttfr_seconds` (time-to-first-review after cutoff, excluding bots and author)
- Optional `ttfc_seconds` exists but default `include_ttfc=False`.

Aggregated:

- Grouped by router risk bucket (`(risk or "unknown").lower()`).

## Slicing / Grouping Strategy {#slicing}

Run-level routing agreement slices (per policy, per router) are computed in:

- `packages/evaluation/src/evaluation_harness/runner_aggregate.py`

Slices and denominators:

- `all`
- `observed`
- `router_nonempty`
- `observed_and_router_nonempty`
- `known_truth` (excludes `unknown_due_to_ingestion_gap` and `policy_unavailable`)
