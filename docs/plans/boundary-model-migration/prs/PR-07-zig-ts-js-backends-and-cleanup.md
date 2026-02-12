# PR-07: Zig + TypeScript/JavaScript Parser Backends and Final Cleanup

## Purpose
Complete initial language support set and remove residual area terminology from code/tests/docs.

## Scope
- Add Zig parser backend.
- Add TS/JS parser backend.
- Full terminology cleanup (`area` → `boundary`) across active inference package.
- Final docs and migration notes update.

## Non-Goals
- Additional languages beyond initial target set.

---

## Exact File-by-File Change List

## New files

1. `packages/inference/src/repo_routing/boundary/parsers/zig.py`
   - Zig backend with imports/symbol/function extraction + diagnostics.

2. `packages/inference/src/repo_routing/boundary/parsers/typescript_javascript.py`
   - TS/JS backend handling module imports/exports and symbol/function extraction.

3. `packages/inference/tests/test_boundary_zig_parser_backend.py`
4. `packages/inference/tests/test_boundary_ts_js_parser_backend.py`

5. `docs/attention-routing/boundary-language-support.md`
   - language matrix, known limitations, parser diagnostics interpretation.

## Modified files

1. `packages/inference/src/repo_routing/boundary/parsers/registry.py`
   - register Zig and TS/JS backends.

2. `packages/inference/src/repo_routing/boundary/inference/hybrid_path_cochange_v1.py`
   - include additional parser channels in signal fusion.

3. `packages/inference/src/repo_routing/predictor/features/*` (targeted touch)
   - remove any remaining `area` key names or comments.

4. `packages/inference/src/repo_routing/analysis/*`
   - remove any remaining `area_*` naming in evidence and model field names.

5. `packages/inference/src/repo_routing/scoring/config.py`
   - ensure no area-named weight keys remain.

6. `packages/inference/src/repo_routing/repo_profile/models.py`
   - replace `AreaModel` naming if still present with boundary-oriented equivalents.

7. `packages/inference/src/repo_routing/repo_profile/builder.py`
   - update any area-derived model naming/output references.

8. `packages/inference/src/repo_routing/exports/__init__.py`
   - remove area exports and replace with boundary exports if needed for experimentation exports.

9. `packages/inference/tests/*` (broad updates)
   - update residual area assertions, fixtures, and key names.

10. `docs/attention-routing/architecture.md`
11. `docs/attention-routing/data_contract.md`
12. `docs/attention-routing/feature-implementation-checklist.md`
13. `docs/attention-routing/tasks/*.md` (targeted replacements)
14. `docs/codebase-experimentation-guide.md`
15. `docs/architecture-brief.md`
   - migrate terminology and contract references to boundary model.

## Deleted files

1. Any remaining area-specific modules in active source paths (if still present after prior PRs), e.g.:
   - `packages/inference/src/repo_routing/mixed_membership/areas/*` (if not removed in PR-05)
   - other area-only helper files discovered by final grep pass.

---

## Final Cleanup Checklist

- [ ] no `area_for_path` imports in active routing code
- [ ] no `pr.areas.*` keys in active feature outputs
- [ ] no `area_overrides.json` hard dependency in runtime path
- [ ] parser backend registry includes Python/Zig/TS-JS
- [ ] boundary docs fully replace area docs

---

## Tests / Validation

- parser backend tests for Zig and TS/JS,
- full inference package test suite,
- targeted eval smoke runs for at least one repo using parser-enabled strategy,
- deterministic output checks with parser channels enabled.

---

## Risks

- Language parser edge cases and dependency complexity.
  - Mitigation: diagnostics-first behavior, fallback channeling, narrow initial language scope.

---

## Acceptance Criteria

- Initial parser language set complete (Python/Zig/TS-JS),
- no residual area terminology in active code paths,
- docs and tests fully boundary-native.
