from __future__ import annotations

from typing import Callable

from .base import BoundaryParserBackend
from .python import PythonAstParserBackend
from .typescript_javascript import TypeScriptJavaScriptRegexParserBackend
from .zig import ZigRegexParserBackend


ParserBackendFactory = Callable[[], BoundaryParserBackend]

_PARSER_BACKEND_FACTORIES: dict[str, ParserBackendFactory] = {}
_PARSER_BACKEND_ALIASES: dict[str, str] = {}


def register_parser_backend(
    *,
    backend_id: str,
    factory: ParserBackendFactory,
    aliases: tuple[str, ...] = (),
) -> None:
    key = backend_id.strip().lower()
    if not key:
        raise ValueError("backend_id cannot be empty")
    _PARSER_BACKEND_FACTORIES[key] = factory
    for alias in aliases:
        alias_key = alias.strip().lower()
        if alias_key:
            _PARSER_BACKEND_ALIASES[alias_key] = key


def available_parser_backends() -> tuple[str, ...]:
    return tuple(sorted(_PARSER_BACKEND_FACTORIES))


def get_parser_backend(backend_id: str) -> BoundaryParserBackend:
    bid = backend_id.strip().lower()
    key = _PARSER_BACKEND_ALIASES.get(bid, bid)
    factory = _PARSER_BACKEND_FACTORIES.get(key)
    if factory is not None:
        return factory()
    raise KeyError(f"unknown boundary parser backend: {backend_id}")


register_parser_backend(
    backend_id="python.ast.v1",
    factory=PythonAstParserBackend,
    aliases=("python",),
)
register_parser_backend(
    backend_id="zig.regex.v1",
    factory=ZigRegexParserBackend,
    aliases=("zig.v1", "zig"),
)
register_parser_backend(
    backend_id="typescript_javascript.regex.v1",
    factory=TypeScriptJavaScriptRegexParserBackend,
    aliases=(
        "typescript_javascript.v1",
        "ts_js.v1",
        "tsjs",
        "typescript",
        "javascript",
    ),
)
