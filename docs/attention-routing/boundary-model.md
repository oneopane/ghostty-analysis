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

## Parser plugin contract

- Parser channel is optional and controlled by strategy config.
- Snapshot root must be explicitly pinned via `parser_snapshot_root`.
- Missing snapshot root in fallback mode records diagnostics and continues.
- Missing snapshot root in strict mode raises deterministic failure.
- Supported backend IDs:
  - `python.ast.v1`
  - `zig.regex.v1`
  - `typescript_javascript.regex.v1`
- See language details in [`boundary-language-support.md`](./boundary-language-support.md).

## Determinism contract

- JSON output is canonicalized with sorted keys.
- Membership rows are sorted before parquet write.
- `model_hash` is sha256 over canonical normalized payload.
- Float rounding for hash canonicalization is fixed in config.
