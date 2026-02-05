# Task 02: Ready-for-review vs needs-author-work

## 1. Task Summary
- **Task ID:** 02
- **Task name:** Ready-for-review vs needs-author-work
- **One-sentence definition:** Predict whether a PR at cutoff should be routed to reviewers now or returned to author iteration first.
- **Label availability status:** Needs definition

## 2. Decision Point
- **Pipeline stage:** D0
- **Decision consumed by:** routing gate + control policy suppression

## 3. Unit of Prediction
- **PR-level**
- Key: (`repo`, `pr_number`, `cutoff`)

## 4. Cutoff-Safe Inputs
- `issue_content_intervals` (title/body), `pull_request_draft_intervals`
- `pull_request_head_intervals`, `pull_request_files`
- `pull_request_review_request_intervals`
- `comments`, `reviews` up to cutoff, `users`
- Gate parsing outputs from PR body (`issue`, `ai_disclosure`, `provenance`)
- Artifacts: `snapshot.json`, `inputs.json`

### Leakage checklist (must pass)
- [x] Inputs limited to `<= cutoff`
- [x] No post-cutoff review outcomes in features
- [x] No merged/closed state as input
- [x] Draft/readiness from interval state at cutoff only
- [x] Human-knowable at cutoff

## 5. Output Contract
```json
{
  "task": "readiness",
  "repo": "owner/name",
  "pr_number": 123,
  "cutoff": "ISO-8601",
  "prob_ready": 0.0,
  "label": "ready_for_review|needs_author_work",
  "evidence": ["is_draft", "recent_head_updates", "gate_fields_missing"]
}
```

## 6. Label Construction
- **Proposed operational label:**
  - `ready_for_review=1` if first eligible action in `(cutoff, cutoff+48h]` is by non-author/non-bot reviewer (`review_submitted` or review comment).
  - `needs_author_work=1` if first action in same window is author head update (`pull_request.synchronize`) or author comment tagged as follow-up.
- Exclude PRs with no qualifying action within 48h (censored).
- Exclude bot-only activity.
- **Fallback proxy:** `ready=1` iff not draft at cutoff and no head update in previous 6h.

## 7. Baselines
- **Baseline A (trivial non-ML):** `ready=1` if draft=false at cutoff.
- **Baseline B (strong heuristic non-ML):** readiness score from {draft flag, gate-field completeness, recent synchronize count, review request presence} with fixed thresholds.

## 8. Primary Metrics
- **F1 (ready class)** to balance false holds vs false routes.
- **Balanced accuracy** for class imbalance robustness.

## 9. Secondary Metrics / Slices
- Draft vs non-draft slice, size slice, docs-only slice, author tenure slice.

## 10. Offline Evaluation Protocol
- Time split by cutoff month.
- Repo-holdout sanity check.
- No negative sampling (binary PR-level).
- Window sensitivity: 24h/48h/72h.

## 11. Online Feasibility
- **MVP:** assistive readiness badge; no automatic blocking.
- Automation only as soft nudge to author when confidence high.

## 12. Failure Modes
- Label conflates reviewer latency with readiness.
- Author may push small fix despite being review-ready.
- Leakage risk if using future request additions as inputs.

## 13. Dependencies / Open Questions
- Need standardized definition of "author-work" events across repos.
- Need policy for conflicting signals (draft=false but active rework).

## 14. Logging / Evidence Requirements
- Log draft state, recent synchronize counts, gate completeness, request counts.
- Log which event created the label for auditability.

## 15. Versioning Notes (candidate generation, schema, label version)
- `task_version`: t02.v1
- `candidate_gen_version`: n/a
- `schema_version`: attention_tasks.v1
- `label_version`: t02.label.v1
- Backward-compatibility notes: if action precedence changes, bump label version.
