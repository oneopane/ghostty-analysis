from __future__ import annotations

import re
from pathlib import Path

from .models import ParsedFileSignals, ParsedFunction, ParsedImport, ParserRunResult

_IMPORT_RE = re.compile(r'@import\(\s*"([^"]+)"\s*\)')
_FUNCTION_RE = re.compile(r"\b(?:pub\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")


class ZigRegexParserBackend:
    backend_id = "zig.regex.v1"
    backend_version = "v1"

    def parse_snapshot(self, *, root: Path, paths: list[str]) -> ParserRunResult:
        files: list[ParsedFileSignals] = []
        diagnostics: list[str] = []

        for rel in sorted(set(paths)):
            if not rel.endswith(".zig"):
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

            imports = sorted({m.strip() for m in _IMPORT_RE.findall(source) if m.strip()})
            functions = sorted({m.strip() for m in _FUNCTION_RE.findall(source) if m.strip()})

            files.append(
                ParsedFileSignals(
                    path=rel,
                    language="zig",
                    imports=[ParsedImport(module=m) for m in imports],
                    functions=[ParsedFunction(name=f) for f in functions],
                )
            )

        return ParserRunResult(
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            files=files,
            diagnostics=sorted(diagnostics),
        )
