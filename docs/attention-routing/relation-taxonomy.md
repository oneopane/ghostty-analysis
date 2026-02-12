# PR×X Relation Taxonomy (source-of-truth)

This document defines the canonical relational framing for attention-routing features.

Core rule:

- Every feature should be understood as either:
  - intrinsic PR state at cutoff, or
  - a relation `(PR_at_cutoff, X) -> signal`.

## Relation families

| Relation type | Canonical question | Current feature families |
|---|---|---|
| PR×PR | Which historical PRs look like this one? | `sim.nearest_prs.*`, `repo.priors.*` |
| PR×User | How strong is this PR↔candidate fit? | `candidate.*`, `pair.*` |
| PR×Team | Which team is most responsible/likely to respond? | owner/request/team slices + optional `routing/team_roster.json` expansion |
| PR×File/Boundary | What code surface does this PR interact with? | `pr.surface.*`, `pr.boundary.*`, `pr.ownership.*` |
| PR×Automation | What machine/system feedback exists? | `automation.*` |
| PR×RepoContext | How does this PR compare to repo constraints/priors? | `repo.priors.*`, `pr.surface.*_zscore_vs_repo`, ownership coverage |
| PR×Time | What phase/trajectory is this PR in? | `pr.trajectory.*`, `pr.attention.*`, `pr.request_overlap.*` |
| PR×Silence | What expected relations are absent? | `pr.silence.*` |

## Relation classification flags

Each relation should be classified in planning and review with these flags:

- `deterministic`: reproducible from cutoff-safe sources
- `text_derived`: derived from text parsing or model compression
- `historical_aggregation`: requires lookback-window summarization
- `policy_only`: used as a constraint/guardrail, not a ranking signal

## v1 signal boundary

Allowed:

- Repository-native, cutoff-safe signals from `history.sqlite` and pinned artifacts.

Disallowed:

- External/social-media/persona data,
- network-time mutable signals in core extraction.

## Notes

- This taxonomy is conceptual and does not replace the concrete feature key registry.
- Feature key classification remains defined in `feature-registry.md` and `features/feature_registry.py`.
