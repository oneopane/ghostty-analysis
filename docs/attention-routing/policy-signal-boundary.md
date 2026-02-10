# Attention-Routing Signal Boundary Policy

## Hard boundary

Core attention-routing extraction and evaluation must use only:

1. `history.sqlite` repository-native data, and
2. deterministic pinned artifacts in `data_dir` (for example CODEOWNERS at base SHA).

## Explicitly disallowed

- Social media signals,
- external persona/profile signals,
- network/API-time mutable data in core feature extraction,
- current checkout state not pinned to cutoff identifiers.

## Rationale

- fairness and governance,
- auditability/explainability,
- deterministic reproducibility,
- reduced privacy and compliance risk.

## LLM policy

- LLM-based logic may be used only through import-path experimental routers.
- Core `repo-routing` feature extraction remains deterministic and dependency-light.
