from __future__ import annotations

import ast
from pathlib import Path

from .models import ParsedFileSignals, ParsedFunction, ParsedImport, ParserRunResult


class PythonAstParserBackend:
    backend_id = "python.ast.v1"
    backend_version = "v1"

    def parse_snapshot(self, *, root: Path, paths: list[str]) -> ParserRunResult:
        files: list[ParsedFileSignals] = []
        diagnostics: list[str] = []

        for rel in sorted(set(paths)):
            if not rel.endswith(".py"):
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

            parsed = ParsedFileSignals(path=rel)
            try:
                tree = ast.parse(source)
                imports: set[str] = set()
                funcs: set[str] = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for n in node.names:
                            if n.name:
                                imports.add(str(n.name))
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports.add(str(node.module))
                    elif isinstance(node, ast.FunctionDef):
                        funcs.add(str(node.name))
                parsed.imports = [ParsedImport(module=m) for m in sorted(imports)]
                parsed.functions = [ParsedFunction(name=f) for f in sorted(funcs)]
            except SyntaxError:
                parsed.diagnostics.append("syntax_error")
            files.append(parsed)

        return ParserRunResult(
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            files=files,
            diagnostics=sorted(diagnostics),
        )
