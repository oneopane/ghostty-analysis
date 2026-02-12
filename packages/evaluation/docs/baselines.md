# Baseline Router Limitations and Caveats

This page documents baseline assumptions, leakage risks, and required inputs.

## General rules

- Always evaluate routers with the same PR cohort and cutoff policy.
- Inputs must be cutoff-safe (`history.sqlite` + pinned artifacts).
- Treat baseline scores as reference points, not absolute quality guarantees.

## Router-by-router caveats

## `mentions`

- Source: PR body `@user` / `@org/team` mentions.
- Strength: simple and deterministic.
- Limitations:
  - sparse on PRs without explicit mentions
  - may reflect social habits rather than true ownership

## `popularity`

- Source: historical reviewer/commenter activity in lookback window.
- Strength: robust fallback in active repos.
- Limitations:
  - favors historically active users
  - weak for novel/rare modules or new contributors

## `codeowners`

- Source: CODEOWNERS rules matched to changed files.
- **Safety requirement:** CODEOWNERS must be loaded from pinned base SHA artifact:
  `data/github/<owner>/<repo>/codeowners/<base_sha>/CODEOWNERS`.
- Leakage warning:
  - Using mutable checkout HEAD (or any non-pinned CODEOWNERS) can leak future
    ownership changes and inflate apparent performance.
- Operational note:
  - if pinned CODEOWNERS is missing, router returns empty/high-risk output.

## `stewards`

- Source: weighted historical activity and scoring config.
- Requirements:
  - `--router-config` / `--config` is required.
- Limitations:
  - sensitive to lookback/weight tuning
  - can overfit repo-specific social structure without careful validation

## Reporting guidance

When sharing results, include:

1. router list and configs,
2. cutoff policy,
3. candidate generation/version metadata,
4. caveats above (especially CODEOWNERS pinning).
