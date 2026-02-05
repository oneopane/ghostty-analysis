from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class AreaOverride:
    pattern: str
    area: str


def default_area_for_path(path: str) -> str:
    """Return the first path segment or '__root__' for root files."""
    if "/" not in path:
        return "__root__"
    parts = [p for p in path.split("/") if p]
    return parts[0] if parts else "__root__"


def _parse_overrides(data: object) -> list[AreaOverride]:
    overrides: list[AreaOverride] = []
    if isinstance(data, dict):
        items: Iterable[tuple[object, object]] = data.items()
        for pattern, area in items:
            overrides.append(AreaOverride(pattern=str(pattern), area=str(area)))
        return overrides
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                if "pattern" in item and "area" in item:
                    overrides.append(
                        AreaOverride(
                            pattern=str(item["pattern"]),
                            area=str(item["area"]),
                        )
                    )
                elif len(item) == 1:
                    pattern, area = next(iter(item.items()))
                    overrides.append(AreaOverride(pattern=str(pattern), area=str(area)))
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                overrides.append(AreaOverride(pattern=str(item[0]), area=str(item[1])))
        return overrides
    raise ValueError("invalid area_overrides.json format")


def load_area_overrides(path: str | Path) -> list[AreaOverride]:
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return _parse_overrides(data)


def load_repo_area_overrides(
    *, repo_full_name: str, data_dir: str | Path = "data"
) -> list[AreaOverride]:
    owner, repo = repo_full_name.split("/", 1)
    base = Path(data_dir)
    path = base / "github" / owner / repo / "routing" / "area_overrides.json"
    return load_area_overrides(path)


def area_for_path(path: str, overrides: list[AreaOverride] | None = None) -> str:
    if overrides:
        for rule in overrides:
            if fnmatch.fnmatchcase(path, rule.pattern):
                return rule.area
    return default_area_for_path(path)
