from __future__ import annotations

from repo_routing.boundary.parsers.zig import ZigRegexParserBackend


def test_zig_backend_parses_imports_and_functions(tmp_path) -> None:  # type: ignore[no-untyped-def]
    root = tmp_path / "snap"
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "main.zig").write_text(
        'const std = @import("std");\n'
        'const util = @import("pkg/util.zig");\n\n'
        'pub fn main() !void {\n'
        '    _ = std.debug.print;\n'
        '}\n\n'
        'fn helper() void {}\n',
        encoding="utf-8",
    )

    backend = ZigRegexParserBackend()
    out = backend.parse_snapshot(root=root, paths=["src/main.zig", "src/ignore.py"])

    assert out.backend_id == "zig.regex.v1"
    assert out.files
    parsed = out.files[0]
    assert parsed.language == "zig"
    assert {i.module for i in parsed.imports} == {"pkg/util.zig", "std"}
    assert [f.name for f in parsed.functions] == ["helper", "main"]
