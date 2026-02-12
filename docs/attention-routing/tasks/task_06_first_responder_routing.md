# Task 06: First-responder routing (team/user ranking)

## 1. Task Summary
- **Task ID:** 06
- **Task name:** First-responder routing (team/user ranking)
- **One-sentence definition:** Rank candidate reviewers/teams so top-ranked targets maximize likelihood of the first eligible post-cutoff response.
- **Label availability status:** Known

## 2. Decision Point
- **Pipeline stage:** D2
- **Decision consumed by:** primary routing recommendation

## 3. Unit of Prediction
- **Candidate-level ranking per PR**
- Key: (`repo`, `pr_number`, `cutoff`, `candidate_id`)

## 4. Cutoff-Safe Inputs
- PR snapshot as-of cutoff (`snapshot.json` / `inputs.json`)
- Interval tables: `issue_content_intervals`, `pull_request_head_intervals`, `pull_request_review_request_intervals`, `pull_request_draft_intervals`
- File/churn surface: `pull_request_files`
- Ownership artifacts: `codeowners/<base_sha>/CODEOWNERS`, boundary model artifacts for the same cutoff
- Historical candidate activity up to cutoff:
  - `reviews`, `comments`, `events`, `users`
- Candidate generation sources (versioned): requested users/teams, CODEOWNERS owners, historically active participants, mention-derived users

### Leakage checklist (must pass)
- [x] Candidate features built with events/tables `<= cutoff`
- [x] No post-cutoff responder/outcome fields in features
- [x] Candidate set frozen by `candidate_gen_version`
- [x] Pinned CODEOWNERS/boundary artifacts used
- [x] Human-knowable at cutoff

## 5. Output Contract
```json
{
  "task": "first_responder_routing",
  "repo": "owner/name",
  "pr_number": 123,
  "cutoff": "ISO-8601",
  "candidate_gen_version": "cg.v1",
  "ranked_candidates": [
    {"target_type": "user|team", "target": "alice", "score": 0.84, "rank": 1}
  ],
  "confidence": "low|medium|high"
}
```

## 6. Label Construction
- **Operational truth alignment (required):**
  - Positive target = **first eligible non-author, non-bot reviewer action after cutoff**.
- Use window `(cutoff, cutoff+14d]`; if no eligible action, sample excluded from ranking metrics and counted in coverage metrics.
- Eligibility:
  - actor type not bot (`users.type != 'Bot'`, plus login `[bot]` guard)
  - actor != PR author
  - qualifying actions: `review_submitted` (and optionally review comment if configured; versioned)
- If first responder not in candidate set, mark as `missed_by_candidate_gen` (separate metric).

## 7. Baselines
- **Baseline A (trivial non-ML):** preserve explicit review request order at cutoff, else lexicographic fallback.
- **Baseline B (strong heuristic non-ML):** CODEOWNERS-first, then recency-weighted historical responder frequency in matching boundaries.

## 8. Primary Metrics
- **MRR** + **Hit@1/3/5** on eligible PRs.
- Justification: directly measures ranking quality for first-response objective.

## 9. Secondary Metrics / Slices
- Repo, boundary, PR size, owner coverage bucket, requested vs unrequested responder, author tenure.
- Candidate-gen coverage: `% truth in pool`.

## 10. Offline Evaluation Protocol
- Time-based split by cutoff; report rolling-window stability.
- Optional repo holdout.
- Candidate set fixed per `candidate_gen_version`; no per-model pool mutation.
- No negative sampling needed (full candidate list ranking).
- Deterministic tie-break: score desc, candidate key asc.

## 11. Online Feasibility
- **MVP:** shadow ranking + evidence traces in artifacts.
- Assistive: suggest top-1/top-3 candidates.
- Automation only with confidence/risk guardrails.

## 12. Failure Modes
- Ground truth mismatch (first responder may not be best owner).
- Candidate generation misses true responder.
- Team/user mixed ranking ambiguity.

## 13. Dependencies / Open Questions
- Need stable team→user expansion policy for mixed target evaluation.
- Need decision whether review comments count as first response.

## 14. Logging / Evidence Requirements
- Log candidate pool composition by source.
- Log top-k scores/evidence features per candidate.
- Log truth target and whether in-pool.

## 15. Versioning Notes (candidate generation, schema, label version)
- `task_version`: t06.v1
- `candidate_gen_version`: cg.v1
- `schema_version`: attention_tasks.v1
- `label_version`: t06.label.v1
- Backward-compatibility notes: qualifying action set or window changes bump label version.
