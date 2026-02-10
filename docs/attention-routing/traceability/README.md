# Transcript → Decision → Implementation Traceability

This folder is the operational source-of-truth for reconciling chat transcripts with implementation.

## Files

- `ideas_registry.jsonl`
  - One deduplicated idea per line.
- `implementation_map.json`
  - Mapping from `idea_id` to code/tests/docs evidence.

## Status values

- `already implemented`
- `partially implemented`
- `not implemented`
- `unclear`

## Workflow

1. Ingest transcript batch.
2. Extract atomic ideas.
3. Deduplicate and assign `idea_id`.
4. Reconcile against code + docs.
5. Update decision docs (`../decisions/DEC-*.md`) when policy-level choices are made.
