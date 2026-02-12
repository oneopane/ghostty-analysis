# Task 08: Candidate non-response / availability prediction

## 1. Task Summary
- **Task ID:** 08
- **Task name:** Candidate non-response / availability prediction
- **One-sentence definition:** Predict the probability that a specific candidate will not provide an eligible review response within SLA after cutoff/request.
- **Label availability status:** Needs definition

## 2. Decision Point
- **Pipeline stage:** D2/D3
- **Decision consumed by:** whether to ping this candidate now, defer, or escalate to alternates

## 3. Unit of Prediction
- **Candidate-level binary classification per PR**
- Key: (`repo`, `pr_number`, `cutoff`, `candidate_id`)

## 4. Cutoff-Safe Inputs
- Candidate/PR features available at cutoff:
  - Historical candidate activity and latency stats from `reviews`, `comments`, `events`, `users`
  - Current PR context from `snapshot.json`, `inputs.json`, `pull_request_files`, interval tables
  - Owner/boundary overlap from `codeowners/<base_sha>/CODEOWNERS` and boundary model artifacts
  - Active request state at cutoff from `pull_request_review_request_intervals`
- Candidate pool from versioned generator (`candidate_gen_version`)

### Leakage checklist (must pass)
- [x] No post-cutoff candidate actions in features
- [x] Request-state feature uses as-of interval only
- [x] No knowledge of eventual responder in inputs
- [x] Pinned ownership artifacts only
- [x] Human-knowable at cutoff

## 5. Output Contract
```json
{
  "task": "candidate_availability",
  "repo": "owner/name",
  "pr_number": 123,
  "cutoff": "ISO-8601",
  "candidate": {"type": "user|team", "name": "alice"},
  "prob_non_response_within_sla": 0.0,
  "sla_hours": 24,
  "decision_hint": "ping|defer|backup"
}
```

## 6. Label Construction
- **Primary label (observationally safer subset):** restrict to candidates explicitly requested at cutoff.
  - `y=1` (non-response) if candidate has **no** eligible non-author/non-bot review action in `(cutoff, cutoff+24h]` on this PR.
  - `y=0` if candidate has at least one eligible action in window.
- **Secondary label (broader, higher counterfactual risk):** same definition over all generated candidates.
- Team candidates:
  - `y=0` if any mapped team member responds (mapping versioned); else `y=1`.
- Exclude bot candidates and PR author identity.
- Censor PRs closed before SLA end.

## 7. Baselines
- **Baseline A (trivial non-ML):** global non-response prior by repo.
- **Baseline B (strong heuristic non-ML):** candidate historical median response-time buckets + recent activity recency + open-request load threshold.

## 8. Primary Metrics
- **PR-AUC** on requested-candidate subset.
- **Brier score / ECE** for calibration at decision thresholds.
- Justification: this score directly controls intervention policy.

## 9. Secondary Metrics / Slices
- Requested vs unrequested, owner vs non-owner, repo, boundary, weekday/hour buckets, candidate activity quantiles.

## 10. Offline Evaluation Protocol
- Build candidate rows from fixed `candidate_gen_version`.
- Time split by cutoff month.
- For class balance, keep all positives and sample negatives with fixed seed for exploratory runs; full-set reporting required for final.
- Report metrics separately for primary (requested-only) and secondary (all-candidates) cohorts.

## 11. Online Feasibility
- **MVP:** assistive “backup candidate” suggestion when predicted non-response is high.
- No auto-ping suppression until calibration quality passes gate.

## 12. Failure Modes
- Strong counterfactual bias for unrequested candidates.
- Team availability depends on noisy membership mapping.
- Could systematically under-route less-active but qualified reviewers.

## 13. Dependencies / Open Questions
- Need canonical team membership snapshot source.
- Need SLA standardization by repo class.
- Need policy on whether comments count as response.

## 14. Logging / Evidence Requirements
- Log per-candidate probability, feature summary, and request-at-cutoff flag.
- Log which cohort (requested-only/all) the score belongs to.

## 15. Versioning Notes (candidate generation, schema, label version)
- `task_version`: t08.v1
- `candidate_gen_version`: cg.v1
- `schema_version`: attention_tasks.v1
- `label_version`: t08.label.v1 (requested-primary)
- Backward-compatibility notes: SLA/window or team mapping changes require label bump.
