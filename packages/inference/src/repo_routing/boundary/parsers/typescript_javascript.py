from __future__ import annotations

import re
from pathlib import Path

from .models import ParsedFileSignals, ParsedFunction, ParsedImport, ParserRunResult

_TS_JS_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}

_IMPORT_FROM_RE = re.compile(
    r"^\s*import(?:\s+type)?(?:[\s\w{},*\n$]+)?\s+from\s+[\"']([^\"']+)[\"']",
    re.MULTILINE,
)
_IMPORT_SIDE_EFFECT_RE = re.compile(
    r"^\s*import\s+[\"']([^\"']+)[\"']", re.MULTILINE
)
_EXPORT_FROM_RE = re.compile(
    r"^\s*export(?:\s+type)?(?:[\s\w{},*\n$]+)?\s+from\s+[\"']([^\"']+)[\"']",
    re.MULTILINE,
)
_REQUIRE_RE = re.compile(r"require\(\s*[\"']([^\"']+)[\"']\s*\)")
_FUNCTION_DECL_RE = re.compile(r"\bfunction\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(")
_ARROW_FUNC_RE = re.compile(
    r"\b(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][A-Za-z0-9_$]*)\s*=>"
)


class TypeScriptJavaScriptRegexParserBackend:
    backend_id = "typescript_javascript.regex.v1"
    backend_version = "v1"

    def parse_snapshot(self, *, root: Path, paths: list[str]) -> ParserRunResult:
        files: list[ParsedFileSignals] = []
        diagnostics: list[str] = []

        for rel in sorted(set(paths)):
            ext = Path(rel).suffix.lower()
            if ext not in _TS_JS_EXTENSIONS:
                continue

            p = root / rel
            if not p.exists():
                diagnostics.append(f"missing:{rel}")
                continue
            try:
                source = p.read_text(encoding="utf-8")
            except Exception:
                diagnostics.append(f"read_error:{rel}")
                continue

            imports = {
                *[m.strip() for m in _IMPORT_FROM_RE.findall(source)],
                *[m.strip() for m in _IMPORT_SIDE_EFFECT_RE.findall(source)],
                *[m.strip() for m in _EXPORT_FROM_RE.findall(source)],
                *[m.strip() for m in _REQUIRE_RE.findall(source)],
            }
            imports = {m for m in imports if m}

            functions = {
                *[m.strip() for m in _FUNCTION_DECL_RE.findall(source)],
                *[m.strip() for m in _ARROW_FUNC_RE.findall(source)],
            }
            functions = {f for f in functions if f}

            language = "typescript" if ext in {".ts", ".tsx"} else "javascript"
            files.append(
                ParsedFileSignals(
                    path=rel,
                    language=language,
                    imports=[ParsedImport(module=m) for m in sorted(imports)],
                    functions=[ParsedFunction(name=f) for f in sorted(functions)],
                )
            )

        return ParserRunResult(
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            files=files,
            diagnostics=sorted(diagnostics),
        )
