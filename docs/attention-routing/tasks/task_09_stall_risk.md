# Task 09: Stall risk escalation trigger

## 1. Task Summary
- **Task ID:** 09
- **Task name:** Stall risk escalation trigger
- **One-sentence definition:** Predict whether a PR is likely to miss first-response SLA and should trigger escalation.
- **Label availability status:** Known

## 2. Decision Point
- **Pipeline stage:** D3
- **Decision consumed by:** escalation/nudge policy timing

## 3. Unit of Prediction
- **PR-level survival/classification**
- Key: (`repo`, `pr_number`, `cutoff`)

## 4. Cutoff-Safe Inputs
- D0/D1/D2 outputs (readiness, size, ownership confidence, routing confidence)
- PR state from intervals and snapshot artifacts (`snapshot.json`, `inputs.json`)
- Historical queue metrics from pre-cutoff events (`reviews`, `comments`, `events`, `users`)
- Candidate availability aggregates from Task 08 (cutoff-safe predictions)

### Leakage checklist (must pass)
- [x] No realized post-cutoff response times in input features
- [x] Only pre-cutoff queue/history stats used
- [x] No final merge state features
- [x] Upstream task inputs must also be cutoff-safe
- [x] Human-knowable at cutoff

## 5. Output Contract
```json
{
  "task": "stall_risk",
  "repo": "owner/name",
  "pr_number": 123,
  "cutoff": "ISO-8601",
  "prob_miss_sla": 0.0,
  "expected_ttfr_hours": 0.0,
  "escalate": true,
  "escalation_level": "none|soft|hard"
}
```

## 6. Label Construction
- Define SLA horizon `H=24h` (configurable per repo class).
- `y=1` (stall risk) if no eligible non-author/non-bot review response occurs in `(cutoff, cutoff+H]`.
- `y=0` if at least one eligible response occurs in window.
- Survival variant: event time = TTFR; censor at PR close or `cutoff+7d`.
- Exclude PRs with missing author identity or bot-authored PRs.

## 7. Baselines
- **Baseline A (trivial non-ML):** constant repo-level miss-SLA rate.
- **Baseline B (strong heuristic non-ML):** fixed escalation if (no active requests at cutoff) OR (oversized) OR (low owner coverage confidence).

## 8. Primary Metrics
- **C-index** (survival ranking quality) and **PR-AUC@SLA**.
- For deployment thresholds: **Brier/ECE** at `H`.

## 9. Secondary Metrics / Slices
- Repo, PR size, owner coverage bucket, requested count, day-of-week, external vs internal author.

## 10. Offline Evaluation Protocol
- Time-split train/val/test.
- Evaluate fixed-horizon and survival variants.
- No negative sampling (PR-level).
- Counterfactual flag required when using policy-conditioned upstream features.

## 11. Online Feasibility
- **MVP:** shadow escalation recommendations with rationale.
- Assistive launch: soft escalation suggestions only.

## 12. Failure Modes
- Escalation policies can become self-fulfilling labels over time.
- High false positives increase ping volume/spam.

## 13. Dependencies / Open Questions
- Need canonical SLA values and escalation budget per repo.
- Need policy for repeated escalation attempts.

## 14. Logging / Evidence Requirements
- Log predicted miss probability, threshold, chosen escalation level, and upstream task snapshots.
- Track downstream outcomes (TTFR, reroute) for policy audits.

## 15. Versioning Notes (candidate generation, schema, label version)
- `task_version`: t09.v1
- `candidate_gen_version`: cg.v1 (via upstream features)
- `schema_version`: attention_tasks.v1
- `label_version`: t09.label.v1
- Backward-compatibility notes: SLA horizon change requires label version bump.
