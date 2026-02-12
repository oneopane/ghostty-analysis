# Task 04: Ownership coverage confidence

## 1. Task Summary
- **Task ID:** 04
- **Task name:** Ownership coverage confidence
- **One-sentence definition:** Estimate confidence that current ownership signals (CODEOWNERS/boundaries/requests) are sufficient to get an eligible owner response within SLA.
- **Label availability status:** Risky

## 2. Decision Point
- **Pipeline stage:** D1
- **Decision consumed by:** whether to trust owner-based routing or widen candidate search/escalation

## 3. Unit of Prediction
- **PR-level**
- Key: (`repo`, `pr_number`, `cutoff`)

## 4. Cutoff-Safe Inputs
- Pinned ownership artifacts:
  - `codeowners/<base_sha>/CODEOWNERS`
  - boundary model artifacts for the same cutoff (`boundary_model.json` + `memberships.parquet`)
- Snapshot state:
  - `pull_request_head_intervals` + `pull_request_files` at head SHA
  - `pull_request_review_request_intervals` active at cutoff
- Historical owner activity up to cutoff:
  - `reviews`, `comments`, `users`
- Optional derived artifacts: `inputs.json` owner coverage summaries

### Leakage checklist (must pass)
- [x] Owner coverage computed from pinned base/head artifacts at cutoff
- [x] Historical activity bounded to `<= cutoff`
- [x] No post-cutoff responder identity in features
- [x] No merge outcome fields in input
- [x] Human-knowable at cutoff

## 5. Output Contract
```json
{
  "task": "owner_coverage_confidence",
  "repo": "owner/name",
  "pr_number": 123,
  "cutoff": "ISO-8601",
  "prob_owner_response_within_sla": 0.0,
  "coverage_bucket": "low|medium|high",
  "owner_set": ["team:infra", "user:alice"],
  "evidence": {"owner_match_ratio": 0.0, "active_owner_count_30d": 0}
}
```

## 6. Label Construction
- **Primary label (observational):**
  - Define owner candidate set `O` from CODEOWNERS/boundary mapping at cutoff (team expansion policy versioned).
  - `y=1` if any eligible non-author/non-bot owner in `O` performs first qualifying review action in `(cutoff, cutoff+24h]`.
  - `y=0` if first qualifying review action in window is by non-owner or no owner action by `cutoff+24h`.
- **Eligibility filters:** exclude PRs with empty owner set (tracked separately as structural low coverage).
- **Fallback proxy label (if owner identity is noisy):** `proxy_high_coverage=1` if `owner_match_ratio=1.0` and `active_owner_count_30d>=2`.

## 7. Baselines
- **Baseline A (trivial non-ML):** confidence from owner-set size only (`|O|==0 low; 1 medium; >=2 high`).
- **Baseline B (strong heuristic non-ML):** rules over owner path coverage, owner recency activity (30/90d), and whether owners already requested at cutoff.

## 8. Primary Metrics
- **Brier score** (probability quality for policy thresholds).
- **PR-AUC** (ranking coverage risk).
- Justification: this task gates downstream escalation decisions, so calibration + discrimination are both required.

## 9. Secondary Metrics / Slices
- Repo, owner-set size, team-owned vs user-owned paths, single-boundary vs multi-boundary PRs, external author slice.

## 10. Offline Evaluation Protocol
- Time-based splits; enforce no leakage across cutoff.
- For team owners, evaluate both team-level and expanded-user label variants.
- Sensitivity study over SLA window (12h/24h/48h).
- Track missing/ambiguous ownership rows separately.

## 11. Online Feasibility
- **MVP:** assistive badge: `coverage=low` triggers recommendation to widen candidate pool.
- No hard blocking in initial rollout.

## 12. Failure Modes
- Team→user expansion introduces noise and stale membership assumptions.
- CODEOWNERS may be outdated relative to actual reviewer behavior.
- Counterfactual risk: owners may respond because they were requested by policy.

## 13. Dependencies / Open Questions
- Need canonical team expansion source/version.
- Need decision on owner correctness definition when multiple overlapping owners exist.

## 14. Logging / Evidence Requirements
- Log owner extraction trace (matched patterns, owner entities).
- Log active owner counts by window and final calibrated probability.
- Persist `owner_definition_version` used at scoring time.

## 15. Versioning Notes (candidate generation, schema, label version)
- `task_version`: t04.v1
- `candidate_gen_version`: cg.v1 (for shared owner/candidate extraction)
- `schema_version`: attention_tasks.v1
- `label_version`: t04.label.v1
- Backward-compatibility notes: any team expansion rule change requires label + task bump.
