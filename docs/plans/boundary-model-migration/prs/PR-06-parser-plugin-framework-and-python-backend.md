# PR-06: Parser Plugin Framework + Python Backend

## Purpose
Add first-class structural parsing extensibility and integrate Python parser signals into boundary inference.

## Scope
- parser backend interface and registry,
- parser signal model contract,
- Python parser backend implementation,
- hybrid strategy integration with parser channel (optional/fallback-safe).

## Non-Goals
- Zig/TS/JS parser backends (PR-07).

---

## Exact File-by-File Change List

## New files

1. `packages/inference/src/repo_routing/boundary/parsers/__init__.py`

2. `packages/inference/src/repo_routing/boundary/parsers/base.py`
   - parser backend protocol and result schema.

3. `packages/inference/src/repo_routing/boundary/parsers/models.py`
   - parsed file signal models (imports, symbols, functions, refs, diagnostics).

4. `packages/inference/src/repo_routing/boundary/parsers/registry.py`
   - backend registration/loading.

5. `packages/inference/src/repo_routing/boundary/parsers/python.py`
   - Python backend (AST-based initial implementation).

6. `packages/inference/src/repo_routing/boundary/signals/parser.py`
   - convert parser outputs into boundary signal edges/features.

7. `packages/inference/src/repo_routing/boundary/source_snapshot.py`
   - source snapshot reader rooted at pinned artifact directories.

8. `packages/inference/tests/test_boundary_parser_registry.py`
9. `packages/inference/tests/test_boundary_python_parser_backend.py`
10. `packages/inference/tests/test_boundary_parser_signal_integration.py`
11. `packages/inference/tests/test_boundary_parser_fallback_behavior.py`

## Modified files

1. `packages/inference/src/repo_routing/boundary/config.py`
   - parser channel config:
     - enable/disable,
     - language allowlist,
     - parser weighting,
     - strict/fallback mode.

2. `packages/inference/src/repo_routing/boundary/inference/hybrid_path_cochange_v1.py`
   - integrate parser signal channel conditionally.

3. `packages/inference/src/repo_routing/boundary/artifacts.py`
   - parser coverage/diagnostics metadata fields.

4. `packages/inference/src/repo_routing/boundary/io.py`
   - include parser signal sidecar artifact handling if enabled.

5. `packages/inference/src/repo_routing/paths.py`
   - helper paths for pinned source artifact discovery if needed.

6. `packages/inference/src/repo_routing/cli/app.py`
   - CLI flags for parser channel toggles and language selection.

7. `packages/experimentation/src/experimentation/unified_experiment.py`
   - optional boundary parser preflight checks (snapshot availability diagnostics).

8. `docs/attention-routing/boundary-model.md`
   - parser plugin contract and fallback semantics.

## Deleted files
- None.

---

## Source Snapshot Contract (v1)

- Parser channel reads from pinned source snapshots only.
- Snapshot root declared in artifact manifest.
- No implicit local checkout reads by default.
- Missing snapshot -> parser channel skipped with diagnostics (unless strict mode).

---

## Tests / Validation

- parser backend deterministic output on identical source,
- parser failure does not break boundary model generation in fallback mode,
- coverage diagnostics included in manifest and stable.

---

## Risks

- Python parser edge cases (syntax/version differences).
  - Mitigation: robust diagnostics + skip-unparseable-file policy.

---

## Acceptance Criteria

- Parser backends are pluggable through registry,
- Python backend integrated and exercised in hybrid strategy,
- parser channel is optional and fallback-safe.
