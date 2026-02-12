# Mixed Membership (Exploration API)

This module is for **offline exploration** (for example in marimo), not mandatory production routing.

Location:

- `packages/inference/src/repo_routing/mixed_membership/`

## Design

- Function-first API (no required scripts)
- Deterministic inputs: repository DB + boundary path partition
- Optional libraries for exploration lane:
  - `polars`
  - `numpy`
  - `scikit-learn`

## Primary APIs

```python
from repo_routing.mixed_membership import (
    BoundaryMembershipConfig,
    build_boundary_membership_dataset,
    fit_boundary_membership_model,
)

cfg = BoundaryMembershipConfig(lookback_days=180, n_components=6)

df = build_boundary_membership_dataset(
    repo="owner/name",
    cutoff=cutoff_dt,
    data_dir="data",
    config=cfg,
    as_polars=True,
)

model = fit_boundary_membership_model(
    repo="owner/name",
    cutoff=cutoff_dt,
    data_dir="data",
    config=cfg,
)
```

## Marimo notebook

A starter notebook is available at:

- `experiments/marimo/mixed_membership_boundaries_v1.py`

## Notes

- This is an experimental subsystem for mixed-membership style inference.
- Boundary-basis is the first production implementation (`hybrid_path_cochange.v1`).
- Keep runtime-critical routing deterministic and dependency-light.
