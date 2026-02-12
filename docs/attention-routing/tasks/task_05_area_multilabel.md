# Task 05: Boundary/module multi-label classification

## 1. Task Summary
- **Task ID:** 05
- **Task name:** Boundary/module multi-label classification
- **One-sentence definition:** Predict the set of impacted boundaries/modules for a PR at cutoff.
- **Label availability status:** Known

## 2. Decision Point
- **Pipeline stage:** D1
- **Decision consumed by:** ownership inference and candidate generation constraints

## 3. Unit of Prediction
- **PR-level multi-label**
- Key: (`repo`, `pr_number`, `cutoff`)

## 4. Cutoff-Safe Inputs
- `pull_request_files` at head SHA as-of cutoff
- `pull_request_head_intervals`
- Pinned boundary artifacts (`boundary_model.json` + `memberships.parquet`)
- Optional `issue_content_intervals` title/body tokens

### Leakage checklist (must pass)
- [x] Labels/features from cutoff file list only
- [x] No post-cutoff reviewer activity features
- [x] Boundary mapping from pinned artifacts only
- [x] No merged outcome inputs
- [x] Human-knowable at cutoff

## 5. Output Contract
```json
{
  "task": "boundary_multilabel",
  "repo": "owner/name",
  "pr_number": 123,
  "cutoff": "ISO-8601",
  "boundaries": ["api", "infra"],
  "boundary_scores": {"api": 0.91, "infra": 0.63}
}
```

## 6. Label Construction
- Deterministic labels from touched file paths at cutoff via boundary model membership projection.
- PR label set = union of mapped boundaries across files.
- Exclude files under ignored globs (if configured).

## 7. Baselines
- **Baseline A (trivial non-ML):** majority boundary only (single label = most common boundary in repo history).
- **Baseline B (strong heuristic non-ML):** deterministic path-based boundary mapping, no learning.

## 8. Primary Metrics
- **Micro-F1** and **Jaccard** for multi-label quality.

## 9. Secondary Metrics / Slices
- Single-label vs multi-label PRs, boundary frequency buckets, repo slices.

## 10. Offline Evaluation Protocol
- Deterministic labels from same mapping; evaluate learned compression/generalization if using text.
- Time split for robustness to boundary drift.

## 11. Online Feasibility
- **MVP:** immediate boundary tags in routing evidence.

## 12. Failure Modes
- Low-signal repositories produce unstable boundary partitions.
- Directory restructures can break mapping continuity.

## 13. Dependencies / Open Questions
- Need governance process for boundary strategy version upgrades.

## 14. Logging / Evidence Requirements
- Log per-file projected boundary memberships.
- Emit final boundary set with confidence/source tags.

## 15. Versioning Notes (candidate generation, schema, label version)
- `task_version`: t05.v1
- `candidate_gen_version`: n/a
- `schema_version`: attention_tasks.v1
- `label_version`: t05.label.v1
- Backward-compatibility notes: mapping rule changes bump label version.
