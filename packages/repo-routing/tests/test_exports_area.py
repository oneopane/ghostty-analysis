from __future__ import annotations

import json
from pathlib import Path

from repo_routing.exports.area import (
    area_for_path,
    default_area_for_path,
    load_area_overrides,
)


def test_default_area_for_path() -> None:
    assert default_area_for_path("src/app.py") == "src"
    assert default_area_for_path("README.md") == "__root__"


def test_area_overrides(tmp_path: Path) -> None:
    p = tmp_path / "area_overrides.json"
    p.write_text(
        json.dumps(
            [
                {"pattern": "docs/**", "area": "docs"},
                {"pattern": "src/**", "area": "core"},
            ]
        ),
        encoding="utf-8",
    )

    overrides = load_area_overrides(p)
    assert area_for_path("docs/readme.md", overrides) == "docs"
    assert area_for_path("src/app.py", overrides) == "core"
    assert area_for_path("README.md", overrides) == "__root__"
