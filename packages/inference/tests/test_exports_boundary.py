from __future__ import annotations

import json
from pathlib import Path

from repo_routing.exports.boundary import (
    boundary_for_path,
    default_boundary_for_path,
    load_boundary_overrides,
)


def test_default_boundary_for_path() -> None:
    assert default_boundary_for_path("src/app.py") == "src"
    assert default_boundary_for_path("README.md") == "__root__"


def test_boundary_overrides(tmp_path: Path) -> None:
    p = tmp_path / "boundary_overrides.json"
    p.write_text(
        json.dumps(
            [
                {"pattern": "docs/**", "boundary": "docs"},
                {"pattern": "src/**", "boundary": "core"},
            ]
        ),
        encoding="utf-8",
    )

    overrides = load_boundary_overrides(p)
    assert boundary_for_path("docs/readme.md", overrides) == "docs"
    assert boundary_for_path("src/app.py", overrides) == "core"
    assert boundary_for_path("README.md", overrides) == "__root__"
