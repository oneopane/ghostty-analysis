# Task 10: Reviewer set sizing (minimal k to hit SLA)

## 1. Task Summary
- **Task ID:** 10
- **Task name:** Reviewer set sizing (minimal k to hit SLA)
- **One-sentence definition:** Estimate the smallest reviewer set size `k` needed so probability of at least one eligible response within SLA exceeds target.
- **Label availability status:** Risky

## 2. Decision Point
- **Pipeline stage:** D3
- **Decision consumed by:** how many reviewers to request/ping

## 3. Unit of Prediction
- **PR-level policy sizing**
- Key: (`repo`, `pr_number`, `cutoff`)

## 4. Cutoff-Safe Inputs
- Ranked candidates from Task 06/07 (cutoff-safe)
- Candidate non-response probabilities from Task 08
- PR-level context from `snapshot.json`, intervals, and size/ownership features
- Candidate generation metadata/version

### Leakage checklist (must pass)
- [x] Uses only pre-cutoff signals and predicted probabilities
- [x] No realized post-cutoff responses in inputs
- [x] Candidate set frozen by version
- [x] No merge outcome features
- [x] Human-knowable at cutoff

## 5. Output Contract
```json
{
  "task": "reviewer_set_sizing",
  "repo": "owner/name",
  "pr_number": 123,
  "cutoff": "ISO-8601",
  "target_sla_hours": 24,
  "target_success_prob": 0.8,
  "recommended_k": 2,
  "expected_success_prob_by_k": {"1": 0.55, "2": 0.81, "3": 0.9}
}
```

## 6. Label Construction
- True counterfactual minimal `k` is unobserved; use proxy construction:
  - For observed requested set size `k_obs`, label `success@k_obs=1` if any eligible response in `(cutoff, cutoff+24h]`, else 0.
- Train/evaluate calibrated success model `P(success@k | top-k set)` over historical observed `k`.
- Derive `recommended_k = min{k: P(success@k) >= target}`.
- **Fallback proxy label:** deterministic from empirical repo curve of success rate vs request count bucket.

## 7. Baselines
- **Baseline A (trivial non-ML):** fixed `k=1` (or repo default).
- **Baseline B (strong heuristic non-ML):** rule table by PR size + owner coverage + stall risk bucket (e.g., k=1/2/3).

## 8. Primary Metrics
- **Calibration of `success@k`** (Brier/ECE) on observed-k cohorts.
- **Ping-efficiency:** achieved SLA success per ping (successes / total requested reviewers).
- Justification: task is a control policy balancing responsiveness vs attention cost.

## 9. Secondary Metrics / Slices
- Repo, area, owner coverage, PR size, requested vs unrequested responder presence.

## 10. Offline Evaluation Protocol
- Time split by cutoff.
- Evaluate only on observed-k support; no extrapolation claims outside support.
- Report policy simulation separately with `counterfactual_risk=true`.

## 11. Online Feasibility
- **MVP:** assistive suggested `k` with confidence band.
- Automation deferred until stable calibration and spam guardrails.

## 12. Failure Modes
- Strong counterfactual bias (historical k chosen by humans/policies).
- Independence assumptions between candidate responses may fail.
- Risk of over-pinging if calibration drifts.

## 13. Dependencies / Open Questions
- Need fixed target success probability by repo tier.
- Need consistent definition of “request” action for set size accounting.

## 14. Logging / Evidence Requirements
- Log recommended `k`, probability curve by `k`, and top-k candidate IDs.
- Track realized response outcome and ping count for policy learning.

## 15. Versioning Notes (candidate generation, schema, label version)
- `task_version`: t10.v1
- `candidate_gen_version`: cg.v1
- `schema_version`: attention_tasks.v1
- `label_version`: t10.label.v1 (observed-k proxy)
- Backward-compatibility notes: changing target SLA/probability requires policy version bump.
