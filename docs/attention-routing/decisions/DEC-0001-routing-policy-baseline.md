# DEC-0001: Routing policy baseline (v1)

- Status: accepted
- Date: 2026-02-09

## Context

Attention-routing needed explicit decisions on truth semantics, signal boundary, relational framing, and reproducibility metadata.

## Decision

1. Behavior truth uses first eligible post-cutoff response in `(cutoff, cutoff+window]`.
   - Default `window=48h`.
   - Qualifying events: review submissions and review-comments (when available).
   - Global filters: exclude bots and PR author.
2. Candidate generation remains versioned (`candidate_gen_version`), and version metadata must be persisted in features and run artifacts when available.
3. Core signal boundary is repository-native only; external/social persona signals are disallowed.
4. Conceptual feature framing is PR×X relations with fixed buckets (PR, user, team, file/area, automation, repo context, time, silence).
5. LLM usage remains import-path experimental; core extraction remains deterministic.

## Consequences

- Truth labels align with forward-looking routing decisions.
- Artifacts and manifests carry stronger traceability.
- Governance boundary is explicit and auditable.

## References

- `docs/attention-routing/relation-taxonomy.md`
- `docs/attention-routing/policy-signal-boundary.md`
- `packages/evaluation-harness/src/evaluation_harness/truth.py`
