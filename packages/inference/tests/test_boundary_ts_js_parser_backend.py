from __future__ import annotations

from repo_routing.boundary.parsers.typescript_javascript import (
    TypeScriptJavaScriptRegexParserBackend,
)
from repo_routing.boundary.signals.parser import parser_boundary_votes


def test_ts_js_backend_parses_imports_functions_and_votes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    root = tmp_path / "snap"
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "a.ts").write_text(
        'import { x } from "@acme/pkg/core";\n'
        'import "./polyfill";\n'
        'export function build() { return x; }\n',
        encoding="utf-8",
    )
    (root / "src" / "b.js").write_text(
        'const fp = require("lodash/fp");\n'
        'const run = () => fp.identity(1);\n',
        encoding="utf-8",
    )

    backend = TypeScriptJavaScriptRegexParserBackend()
    out = backend.parse_snapshot(root=root, paths=["src/a.ts", "src/b.js"])

    assert out.backend_id == "typescript_javascript.regex.v1"
    assert len(out.files) == 2

    by_path = {f.path: f for f in out.files}
    assert by_path["src/a.ts"].language == "typescript"
    assert by_path["src/b.js"].language == "javascript"
    assert {i.module for i in by_path["src/a.ts"].imports} == {"./polyfill", "@acme/pkg/core"}
    assert [f.name for f in by_path["src/a.ts"].functions] == ["build"]
    assert {i.module for i in by_path["src/b.js"].imports} == {"lodash/fp"}
    assert [f.name for f in by_path["src/b.js"].functions] == ["run"]

    votes = parser_boundary_votes(out)
    assert "dir:pkg" in votes["src/a.ts"]
    assert "dir:src" in votes["src/a.ts"]
    assert "dir:lodash" in votes["src/b.js"]
