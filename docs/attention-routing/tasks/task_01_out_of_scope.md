# Task 01: Out-of-scope / wrong-repo detection

## 1. Task Summary
- **Task ID:** 01
- **Task name:** Out-of-scope / wrong-repo detection
- **One-sentence definition:** Predict whether a PR should be excluded from normal reviewer routing because it appears out-of-scope for the repo’s ownership/process boundaries.
- **Label availability status:** Risky

## 2. Decision Point
- **Pipeline stage:** D0
- **Decision consumed by:** triage gate (route vs hold/manual triage)

## 3. Unit of Prediction
- **PR-level**
- Key: (`repo`, `pr_number`, `cutoff`)

## 4. Cutoff-Safe Inputs
- `pull_requests`, `issues`, `issue_content_intervals` (title/body as-of cutoff)
- `pull_request_draft_intervals`, `pull_request_head_intervals`
- `pull_request_files` at head SHA as-of cutoff
- `pull_request_review_request_intervals`
- `users` (author type)
- Pinned artifacts:
  - `codeowners/<base_sha>/CODEOWNERS`
  - `artifacts/routing/boundary_model/<strategy_id>/<cutoff_key>/...`
  - `snapshot.json`, `inputs.json` (per eval run)

### Leakage checklist (must pass)
- [x] Inputs computed with timestamps/events `<= cutoff`
- [x] No merge/close outcome fields in inputs
- [x] No post-cutoff responder-derived features
- [x] CODEOWNERS loaded from pinned `base_sha`
- [x] Human-knowable at cutoff

## 5. Output Contract
```json
{
  "task": "out_of_scope",
  "repo": "owner/name",
  "pr_number": 123,
  "cutoff": "ISO-8601",
  "prob_out_of_scope": 0.0,
  "label": "in_scope|out_of_scope",
  "reasons": ["no_owner_match", "cross_repo_path_signal"]
}
```

## 6. Label Construction
- **Primary (noisy) label:** `out_of_scope=1` if, within `(cutoff, cutoff+7d]`, PR receives explicit maintainer signal of wrong scope (configured regex on maintainer comments/labels) and no valid owner request is added.
- **Negative:** PR receives at least one eligible non-author/non-bot review or owner request in `(cutoff, cutoff+7d]`.
- **Eligibility filters:** exclude author/bot actors; exclude PRs closed within 10 minutes as accidental duplicates.
- **Fallback proxy label (recommended):** deterministic `proxy_out_of_scope=1` if zero CODEOWNERS matches on changed files **and** zero mapped boundaries from boundary artifacts.

## 7. Baselines
- **Baseline A (trivial non-ML):** Always in-scope (`out_of_scope=0`).
- **Baseline B (strong heuristic non-ML):** Mark out-of-scope if no owner match + no requested reviewers at cutoff + path entropy above threshold.

## 8. Primary Metrics
- **PR-AUC** for ranking risk.
- **Recall at high precision (>=0.9 precision)** to minimize false escalations.

## 9. Secondary Metrics / Slices
- By repo, author org-member vs external, docs-only vs code PRs, size buckets, owner coverage buckets.

## 10. Offline Evaluation Protocol
- Time split: train/val/test by cutoff month.
- Repo-holdout evaluation for portability.
- No candidate sampling needed (PR-level binary).
- Deterministic regex/label dictionaries versioned in manifest.

## 11. Online Feasibility
- **MVP:** shadow-only risk flag in D0 triage panel.
- Promote to assistive only after precision gate on false blocks.

## 12. Failure Modes
- Ground truth mismatch (maintainer comments not standardized).
- External contributors may be over-flagged.
- Leakage risk if using post-cutoff closure reason text as input (forbidden).

## 13. Dependencies / Open Questions
- Need maintained taxonomy of “wrong repo/scope” labels/comments.
- Need policy on what action is allowed when high risk is predicted.

## 14. Logging / Evidence Requirements
- Log owner-match counts, boundary coverage count, request-count-at-cutoff, and reasons list.
- Store label source (`explicit|proxy`) for audit.

## 15. Versioning Notes (candidate generation, schema, label version)
- `task_version`: t01.v1
- `candidate_gen_version`: n/a
- `schema_version`: attention_tasks.v1
- `label_version`: t01.label.v1 (explicit+proxy)
- Backward-compatibility notes: keep proxy logic stable or bump label version.
