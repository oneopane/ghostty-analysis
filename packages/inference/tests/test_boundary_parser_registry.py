from __future__ import annotations

import pytest

from repo_routing.boundary.parsers.registry import get_parser_backend


def test_parser_registry_loads_python_backend() -> None:
    backend = get_parser_backend("python.ast.v1")
    assert backend.backend_id == "python.ast.v1"


def test_parser_registry_loads_zig_backend() -> None:
    backend = get_parser_backend("zig")
    assert backend.backend_id == "zig.regex.v1"


def test_parser_registry_loads_ts_js_backend() -> None:
    backend = get_parser_backend("typescript_javascript.v1")
    assert backend.backend_id == "typescript_javascript.regex.v1"


def test_parser_registry_rejects_unknown_backend() -> None:
    with pytest.raises(KeyError):
        get_parser_backend("unknown.backend")
