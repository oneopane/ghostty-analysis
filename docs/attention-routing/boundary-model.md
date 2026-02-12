# Boundary Model Contract (v1)

This document defines the boundary artifact contract introduced for the area → boundary migration.

## Core schema

`BoundaryModel` (JSON: `boundary_model.json`) includes:

- `schema_version`
- `strategy_id`
- `strategy_version`
- `repo`
- `cutoff_utc`
- `membership_mode` (`hard`, `overlap`, `mixed`)
- `units[]`
- `boundaries[]`
- `memberships[]`
- `metadata`

## Artifact layout

Boundary artifacts are written under:

`data/github/<owner>/<repo>/artifacts/routing/boundary_model/<strategy_id>/<cutoff_key>/`

Files:

- `boundary_model.json`
- `memberships.parquet`
- `signals.parquet` (optional)
- `manifest.json`

## Determinism contract

- JSON output is canonicalized with sorted keys.
- Membership rows are sorted before parquet write.
- `model_hash` is sha256 over canonical normalized payload.
- Float rounding for hash canonicalization is fixed in config.
