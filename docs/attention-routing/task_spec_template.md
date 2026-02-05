# Task Spec Template (Attention Routing)

## 1. Task Summary
- **Task ID:**
- **Task name:**
- **One-sentence definition:**
- **Label availability status:** Known / Needs definition / Risky

## 2. Decision Point
- **Pipeline stage:** D0 / D1 / D2 / D3
- **Decision consumed by:** (router, policy, escalation, UI)

## 3. Unit of Prediction
- PR-level / candidate-level / set-level
- Canonical key (e.g., `repo`, `pr_number`, `cutoff`, `candidate`)

## 4. Cutoff-Safe Inputs
- List exact tables/artifacts/features; include timestamp bounds.
- Use pinned artifacts at base/head SHA where applicable.
- Example source names:
  - Interval tables (`issue_content_intervals`, `pull_request_head_intervals`, `pull_request_review_request_intervals`, ...)
  - History tables (`pull_requests`, `reviews`, `comments`, `events`, `users`)
  - Pinned artifacts (`codeowners/<base_sha>/CODEOWNERS`, `routing/area_overrides.json`, `snapshot.json`, `inputs.json`)

### Leakage checklist (must pass)
- [ ] Every input computable with data `<= cutoff`.
- [ ] No merged/closed/outcome fields used as model input.
- [ ] No feature directly/indirectly encodes post-cutoff responder.
- [ ] File-derived context uses pinned SHA artifacts, not current checkout.
- [ ] “Human-knowable at cutoff” sanity check passes.

## 5. Output Contract
- JSON-like schema (concise, deterministic field names/types).
- Include confidence/probability if used by policy thresholds.

## 6. Label Construction
- Exact positive/negative definition.
- Timestamp boundaries (`(cutoff, cutoff+window]`, etc.).
- Eligibility filters (non-author, non-bot, actor type, repo filters).
- Missing-label handling and exclusions.

## 7. Baselines
- **Baseline A (trivial non-ML):**
- **Baseline B (strong heuristic non-ML):**
- Optional ML baseline.

## 8. Primary Metrics
- Metric(s) used for go/no-go and why.

## 9. Secondary Metrics / Slices
- Required slices (repo, area, PR size, ownership coverage, requested vs unrequested, etc.).

## 10. Offline Evaluation Protocol
- Dataset inclusion/exclusion rules.
- Time/repo split strategy.
- Candidate set definition/version.
- Negative sampling strategy (if needed).
- Determinism requirements (manifest + seed + tie-breaks).

## 11. Online Feasibility
- MVP integration surface (shadow/assistive/automation).
- Required latency and observability notes.

## 12. Failure Modes
- Expected error modes.
- Fairness/load concerns.
- Counterfactual caveats where relevant.

## 13. Dependencies / Open Questions
- Upstream contracts, schema dependencies, unresolved policy choices.

## 14. Logging / Evidence Requirements
- What to log per prediction to debug/evaluate.
- Minimal evidence payload for audits.

## 15. Versioning Notes (candidate generation, schema, label version)
- `task_version`:
- `candidate_gen_version`:
- `schema_version`:
- `label_version`:
- Backward-compatibility notes:
