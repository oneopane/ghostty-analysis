# Artifact Types and Cache Keys (V2)

## Core artifact types

- `pr_snapshot`: cutoff-safe snapshot of PR state at evaluation time.
- `pr_inputs`: router input bundle derived from snapshot + repository context.
- `truth_label`: truth policy outputs and diagnostics for a PR/cutoff.
- `route_result`: router output payload and metadata.
- `gate_metrics`: merge/gate policy measurements.
- `queue_metrics`: response-latency metrics.
- `routing_metrics`: per-PR agreement metrics (Hit@k, MRR).

## Common cache key patterns

- Truth policy:
  - `truth:{repo}:{pr_number}:{cutoff_iso}:{policy_id}`
- Route output:
  - `route:{router_id}:{repo}:{pr_number}:{cutoff_iso}`
- Semantic backfill (planned output keying):
  - `{repo}|{entity_type}|{entity_id}|{cutoff}|{artifact_type}|{version_key}`

## Version key components

A `VersionKey` may include:

- `operator_id`
- `operator_version`
- `schema_version`
- `model_id`
- `prompt_id`
- `prompt_version`
- `prompt_hash`
- `temperature`
- `top_p`

These fields define semantic identity for cache safety and provenance.
