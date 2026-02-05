# Task 03: Oversized PR detection

## 1. Task Summary
- **Task ID:** 03
- **Task name:** Oversized PR detection
- **One-sentence definition:** Predict whether a PR exceeds routing-safe size/complexity thresholds and should trigger alternate handling.
- **Label availability status:** Known

## 2. Decision Point
- **Pipeline stage:** D0
- **Decision consumed by:** control policy (split recommendation, larger reviewer set, escalation)

## 3. Unit of Prediction
- **PR-level**
- Key: (`repo`, `pr_number`, `cutoff`)

## 4. Cutoff-Safe Inputs
- `pull_request_files` at cutoff head SHA: `n_changed_files`, `additions`, `deletions`, `changes`
- `pull_request_head_intervals`, `pull_request_draft_intervals`
- `issue_content_intervals` (title/body length features)
- `routing/area_overrides.json` derived area count
- `snapshot.json`, `inputs.json`

### Leakage checklist (must pass)
- [x] All size/churn from head SHA as-of cutoff
- [x] No post-cutoff review latency features
- [x] No merged outcome fields in input
- [x] Pinned path/area mapping only
- [x] Human-knowable at cutoff

## 5. Output Contract
```json
{
  "task": "oversized_pr",
  "repo": "owner/name",
  "pr_number": 123,
  "cutoff": "ISO-8601",
  "prob_oversized": 0.0,
  "label": "normal|oversized",
  "size_features": {"files": 0, "changes": 0, "areas": 0}
}
```

## 6. Label Construction
- **Policy label (deterministic):** `oversized=1` if any:
  - `n_changed_files > 40`
  - `total_changes > 1200`
  - `n_areas > 3`
- Else `oversized=0`.
- Optional learned target: poor responsiveness proxy (`ttfr > 48h`) for oversized calibration studies.

## 7. Baselines
- **Baseline A (trivial non-ML):** fixed single threshold on `total_changes`.
- **Baseline B (strong heuristic non-ML):** weighted rules over files/churn/areas with repo-specific thresholds.

## 8. Primary Metrics
- **Precision@policy-threshold** (avoid over-flagging).
- Secondary for ranking: PR-AUC.

## 9. Secondary Metrics / Slices
- Repo, area count bucket, docs vs code, language/path families.

## 10. Offline Evaluation Protocol
- Deterministic labels from cutoff snapshot (no future window needed).
- Time split for threshold stability checks.
- Compare global vs repo-specific thresholds.

## 11. Online Feasibility
- **MVP:** immediate D0 badge + route policy override (assistive).

## 12. Failure Modes
- Large generated/vendor files can inflate size unfairly.
- Small but high-risk PRs missed by size-only rules.
- Leakage risk low if strictly cutoff snapshot based.

## 13. Dependencies / Open Questions
- Need canonical ignored-path patterns (generated files, lockfiles).

## 14. Logging / Evidence Requirements
- Log raw size stats and threshold decision path.

## 15. Versioning Notes (candidate generation, schema, label version)
- `task_version`: t03.v1
- `candidate_gen_version`: n/a
- `schema_version`: attention_tasks.v1
- `label_version`: t03.label.v1 (policy)
- Backward-compatibility notes: threshold changes require label version bump.
