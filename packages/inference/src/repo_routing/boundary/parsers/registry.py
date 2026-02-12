from __future__ import annotations

from .base import BoundaryParserBackend
from .python import PythonAstParserBackend
from .typescript_javascript import TypeScriptJavaScriptRegexParserBackend
from .zig import ZigRegexParserBackend


def get_parser_backend(backend_id: str) -> BoundaryParserBackend:
    bid = backend_id.strip().lower()
    if bid in {"python.ast.v1", "python"}:
        return PythonAstParserBackend()
    if bid in {"zig.regex.v1", "zig.v1", "zig"}:
        return ZigRegexParserBackend()
    if bid in {
        "typescript_javascript.regex.v1",
        "typescript_javascript.v1",
        "ts_js.v1",
        "tsjs",
        "typescript",
        "javascript",
    }:
        return TypeScriptJavaScriptRegexParserBackend()
    raise KeyError(f"unknown boundary parser backend: {backend_id}")
