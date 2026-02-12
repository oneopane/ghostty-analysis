from __future__ import annotations

from repo_routing.boundary.parsers.python import PythonAstParserBackend


def test_python_backend_parses_imports_and_functions(tmp_path) -> None:
    root = tmp_path / "snap"
    root.mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "a.py").write_text(
        "import os\nfrom collections import Counter\n\ndef f():\n    return 1\n",
        encoding="utf-8",
    )

    backend = PythonAstParserBackend()
    out = backend.parse_snapshot(root=root, paths=["src/a.py"])

    assert out.files
    parsed = out.files[0]
    assert {i.module for i in parsed.imports} == {"collections", "os"}
    assert [f.name for f in parsed.functions] == ["f"]
