# Task 07: Owner-compliant constrained routing

## 1. Task Summary
- **Task ID:** 07
- **Task name:** Owner-compliant constrained routing
- **One-sentence definition:** Rank candidates under an explicit ownership constraint so recommendations stay compliant with CODEOWNERS/area policy.
- **Label availability status:** Known

## 2. Decision Point
- **Pipeline stage:** D2
- **Decision consumed by:** policy-safe routing path when owner compliance is required

## 3. Unit of Prediction
- **Candidate-level ranking per PR (constrained pool)**
- Key: (`repo`, `pr_number`, `cutoff`, `candidate_id`)

## 4. Cutoff-Safe Inputs
- All Task 06 inputs, plus explicit owner constraint set from:
  - `codeowners/<base_sha>/CODEOWNERS`
  - `routing/area_overrides.json`
- Active requests at cutoff from `pull_request_review_request_intervals`
- Historical owner activity from `reviews`/`comments` up to cutoff

### Leakage checklist (must pass)
- [x] Constraint set computed from pinned as-of artifacts
- [x] Historical features bounded to `<= cutoff`
- [x] No post-cutoff response indicators in features
- [x] Candidate pool version fixed
- [x] Human-knowable at cutoff

## 5. Output Contract
```json
{
  "task": "owner_constrained_routing",
  "repo": "owner/name",
  "pr_number": 123,
  "cutoff": "ISO-8601",
  "constraint": {"mode": "owner_only", "owner_set_size": 4},
  "ranked_candidates": [
    {"target_type": "user|team", "target": "alice", "score": 0.77, "rank": 1}
  ],
  "fallback_allowed": true
}
```

## 6. Label Construction
- Truth target same as Task 06 (first eligible non-author/non-bot reviewer action in `(cutoff, cutoff+14d]`).
- Evaluate only PRs with non-empty owner constraint set.
- If truth actor is outside owner set, mark as `owner_mismatch_case` and score with both:
  - strict metric (counts miss)
  - relaxed diagnostic metric (separate)

## 7. Baselines
- **Baseline A (trivial non-ML):** owner list order from CODEOWNERS parsing (deterministic).
- **Baseline B (strong heuristic non-ML):** within owner set, rank by recency-weighted owner activity overlap with PR areas.

## 8. Primary Metrics
- **MRR (owner-constrained)**
- **Owner-hit@k** (k=1/3/5)
- Justification: checks quality while preserving compliance.

## 9. Secondary Metrics / Slices
- Owner-set size buckets, team-only vs user-only owners, overlap depth, requested-owner vs unrequested-owner cases.

## 10. Offline Evaluation Protocol
- Time split identical to Task 06.
- Candidate set definition: intersection of `candidate_gen_version` pool and owner constraint set.
- No negative sampling; full constrained ranking.
- Report coverage loss due to constraints.

## 11. Online Feasibility
- **MVP:** assistive owner-safe top-k list with fallback suggestion when owner pool weak.

## 12. Failure Modes
- Outdated CODEOWNERS causes forced low-quality recommendations.
- Team ownership without reliable expansion reduces user-level precision.

## 13. Dependencies / Open Questions
- Need authoritative team roster snapshots for reproducible expansion.
- Need policy for constrained fallback to non-owner candidates.

## 14. Logging / Evidence Requirements
- Log owner constraint derivation and candidate pruning reasons.
- Log strict vs relaxed evaluation flags.

## 15. Versioning Notes (candidate generation, schema, label version)
- `task_version`: t07.v1
- `candidate_gen_version`: cg.v1
- `schema_version`: attention_tasks.v1
- `label_version`: t07.label.v1 (inherits t06 truth)
- Backward-compatibility notes: constraint semantics changes require task version bump.
