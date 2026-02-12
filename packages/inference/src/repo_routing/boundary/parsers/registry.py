from __future__ import annotations

from .base import BoundaryParserBackend
from .python import PythonAstParserBackend


def get_parser_backend(backend_id: str) -> BoundaryParserBackend:
    bid = backend_id.strip().lower()
    if bid in {"python.ast.v1", "python"}:
        return PythonAstParserBackend()
    raise KeyError(f"unknown boundary parser backend: {backend_id}")
