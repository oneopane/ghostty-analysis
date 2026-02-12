# Feature Implementation Checklist (current state)

This checklist tracks the implemented feature stack in `inference` and highlights remaining gaps.

Updated for current code in:

- `packages/inference/src/repo_routing/predictor/feature_extractor_v1.py`
- `packages/inference/src/repo_routing/predictor/features/*.py`

---

## Implemented families

## A) PR-local

- [x] `pr.meta.*`
- [x] `pr.surface.*`
- [x] `pr.gates.*`

Notes:
- Includes deterministic ordering and sorted map/set outputs.
- Includes lightweight shape geometry keys (`pr.geometry.shape.*`).
- Legacy aliases (`pr.files.*`, `pr.churn.*`, `pr.paths.*`, `pr.text.*`) are still emitted for compatibility.

## B) PR trajectory / attention

- [x] `pr.trajectory.*`
- [x] `pr.attention.*`
- [x] `pr.request_overlap.*`
- [x] `pr.silence.*`

Notes:
- SQL-backed as-of features are cutoff bounded.
- Includes lightweight trajectory geometry keys (`pr.geometry.trajectory.*`).
- `pr.timeline.*` compatibility keys are still emitted.

## C) Ownership / boundaries

- [x] `pr.boundary.*`
- [x] `pr.ownership.*`

Notes:
- CODEOWNERS is loaded from pinned `base_sha` artifact path.
- Legacy `pr.owners.*` aliases still emitted.

## D) Repo priors

- [x] `repo.priors.*`
- [x] normalization keys:
  - `pr.surface.files_zscore_vs_repo`
  - `pr.surface.churn_zscore_vs_repo`

## E) Candidate

- [x] `candidate.profile.*`
- [x] `candidate.activity.*`
- [x] `candidate.footprint.*`

Notes:
- Includes `account_age_days`, `open_reviews_est`, sparse top-N maps for boundary/dir/path.
- Legacy `cand.activity.*` aliases still emitted.

## F) Pairwise PR×Candidate

- [x] `pair.affinity.*`
- [x] `pair.social.*`
- [x] `pair.availability.*`

Notes:
- Includes overlap, owner/request/mention match, atlas dot products.
- Includes social interaction counts and latency median.

## G) PR×PR similarity

- [x] `sim.nearest_prs.*`

Notes:
- Includes top-k ids, mean TTFR, owner overlap rate, common reviewers/boundaries.

## H) Automation

- [x] `automation.*`

Notes:
- Regex-based category tagging for lint/test/security/cla/dep_update.

## I) Labels/debug/evidence fields

- [x] `debug.*` family/version/source-hash fields
- [x] `labels.*` placeholders in extractor output

Notes:
- Labels are emitted as placeholders in extraction output; truth population remains evaluation-time.

---

## Registry and policy layer

- [x] Feature registry implemented:
  - `features/feature_registry.py`
  - taxonomy dimensions: value type, temporal semantics, granularity, role
  - extractor emits `meta.feature_registry` coverage report

- [x] Task policy registry implemented:
  - `features/task_policy.py`
  - policies for `T02`, `T04`, `T06`, `T09`, `T10`
  - extractor can emit `meta.task_policy` when `task_id` is set in config

---

## Policy boundary

- [x] Repository-native only signal policy documented
- [x] External/social persona signals explicitly disallowed in core extraction

## Remaining optional / higher-risk work

- [ ] LLM text compression/tagging (v3)
- [ ] LLM shortlist reranking (v3)
- [ ] additional automation taxonomy refinement beyond regex heuristics

---

## Validation commands

```bash
./.venv/bin/pytest -q packages/inference/tests
./.venv/bin/pytest -q packages/evaluation/tests
```
