# Boundary Parser Language Support (v1)

This document summarizes parser backend support for boundary inference parser signals.

## Supported backends

| Backend ID | Languages | Extraction | Notes |
|---|---|---|---|
| `python.ast.v1` | Python (`.py`) | imports + function names | Uses Python AST parsing. |
| `zig.regex.v1` | Zig (`.zig`) | `@import(...)` + `fn` names | Regex-based parser; diagnostics-first behavior. |
| `typescript_javascript.regex.v1` | TypeScript/JavaScript (`.ts`, `.tsx`, `.js`, `.jsx`, `.mjs`, `.cjs`) | import/export/require modules + function/arrow names | Regex-based parser; deterministic fallback when parsing is unavailable. |

## Runtime behavior

Parser channel is optional in `hybrid_path_cochange.v1`:

- `parser_enabled=true` enables parser signal fusion.
- `parser_backend_id=<backend>` selects backend.
- `parser_snapshot_root=<path>` points to pinned source snapshot root.
- `parser_weight=<float>` controls parser-channel score contribution.
- `parser_strict=true` fails inference when parser channel cannot run.

When parser is unavailable and strict mode is off, inference falls back to path+cochange only and records parser diagnostics.

## Diagnostics interpretation

Common diagnostics:

- `parser_snapshot_missing` — configured snapshot root does not exist.
- `missing:<path>` — expected file not present in snapshot root.
- `read_error:<path>` — file exists but could not be read.
- `parser_backend_error:<ExceptionType>` — backend initialization or parse failure.

Manifest parser coverage fields (`manifest.json`):

- `parser_coverage.enabled`
- `parser_coverage.backend_id`
- `parser_coverage.backend_version`
- `parser_coverage.signal_files`
- `parser_coverage.file_count`
- `parser_coverage.coverage_ratio`
- `parser_coverage.diagnostics[]`
