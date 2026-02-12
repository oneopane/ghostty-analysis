# 003 - Define strict as-of HistoryReader contract

- [ ] Done

## Goal
Expose a single, supported read interface for the history DB that enforces `as_of` cutoffs (leakage-safe by construction).

## Work
- Define `HistoryReader(db_path)` and `HistoryReader.pr_context(pr, as_of) -> PRContext`.
- Ensure all reads use as-of interval semantics (never “latest row” semantics).
- Provide helper methods to list PRs in a time window deterministically.

## Files
Create:
- `packages/inference/src/repo_routing/history/__init__.py`
- `packages/inference/src/repo_routing/history/reader.py`
- `packages/inference/src/repo_routing/history/index.py`
- `packages/inference/src/repo_routing/history/models.py`

## Acceptance Criteria
- The API can build PR context as-of any cutoff timestamp.
- PR context uses stable ordering for events: `(occurred_at, event_id)`.
- Callers (evaluation) do not need ad-hoc SQL.
