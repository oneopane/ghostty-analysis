# Evaluation Metric Definitions

This document defines metrics emitted by the evaluation harness.

## Cutoff and truth conventions

- Unit: `(repo, pr_number, cutoff)`
- Default cutoff policy: `created_at`
- Behavior truth (default): first eligible post-cutoff response in
  `(cutoff, cutoff+truth_window]`, where `truth_window` defaults to 60 minutes
- First-response sources (default): `review_submitted` and `review_comment`
- Eligibility defaults:
  - exclude PR author
  - exclude bots (`users.type == 'Bot'` or login ends with `[bot]`)

## 1) Routing agreement

Computed per router from ranked candidates and truth targets.

Let `rank` be the 1-indexed position of the first truth target in the router list.
If no truth target appears, `rank = None`.

Per-PR metrics:

- `hit@1 = 1 if rank <= 1 else 0`
- `hit@3 = 1 if rank <= 3 else 0`
- `hit@5 = 1 if rank <= 5 else 0`
- `MRR = 1/rank` if rank exists, else `0`

Run-level summary is arithmetic mean across PRs.

## 2) Gate correlation

For each PR, parse gate fields from PR body:

- missing issue reference
- missing AI disclosure
- missing provenance declaration

Also compute `merged` as-of cutoff from events (`pull_request.merged` at or before cutoff).

For each gate field, report:

- `n`, `missing_n`, `present_n`
- `missing_rate`
- `merged_rate_missing`
- `merged_rate_present`

Interpretation: descriptive correlation only (not causal).

## 3) Queue metrics

Per router and PR:

- `ttfr_seconds`: time from cutoff to first eligible review submission at/after cutoff
- `ttfc_seconds` (optional): time from cutoff to first eligible comment at/after cutoff

Eligibility applies same bot/author filters.

Aggregated by router risk bucket (`low` / `medium` / `high` / `unknown`):

- bucket count `n`
- mean `ttfr_seconds`
- mean `ttfc_seconds` (if enabled)

## 4) Notes on interpretation

- If truth is absent for a PR, routing metrics still include that PR
  (it contributes 0 hits and 0 MRR).
- Queue metrics depend on observed activity after cutoff; missing response yields null
  TTFR/TTFC for that PR.
- Compare routers on identical PR cohorts and cutoff policies.
