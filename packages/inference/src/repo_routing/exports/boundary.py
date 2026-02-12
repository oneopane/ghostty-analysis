from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class BoundaryOverride:
    pattern: str
    boundary: str


def default_boundary_for_path(path: str) -> str:
    """Return the first path segment or '__root__' for root files."""
    if "/" not in path:
        return "__root__"
    parts = [p for p in path.split("/") if p]
    return parts[0] if parts else "__root__"


def _parse_overrides(data: object) -> list[BoundaryOverride]:
    overrides: list[BoundaryOverride] = []
    if isinstance(data, dict):
        items: Iterable[tuple[object, object]] = data.items()
        for pattern, boundary in items:
            overrides.append(BoundaryOverride(pattern=str(pattern), boundary=str(boundary)))
        return overrides

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                if "pattern" in item and "boundary" in item:
                    overrides.append(
                        BoundaryOverride(
                            pattern=str(item["pattern"]),
                            boundary=str(item["boundary"]),
                        )
                    )
                elif len(item) == 1:
                    pattern, boundary = next(iter(item.items()))
                    overrides.append(
                        BoundaryOverride(pattern=str(pattern), boundary=str(boundary))
                    )
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                overrides.append(
                    BoundaryOverride(pattern=str(item[0]), boundary=str(item[1]))
                )
        return overrides

    raise ValueError("invalid boundary_overrides.json format")


def load_boundary_overrides(path: str | Path) -> list[BoundaryOverride]:
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return _parse_overrides(data)


def load_repo_boundary_overrides(
    *, repo_full_name: str, data_dir: str | Path = "data"
) -> list[BoundaryOverride]:
    owner, repo = repo_full_name.split("/", 1)
    base = Path(data_dir)
    path = base / "github" / owner / repo / "routing" / "boundary_overrides.json"
    return load_boundary_overrides(path)


def boundary_for_path(path: str, overrides: list[BoundaryOverride] | None = None) -> str:
    if overrides:
        for rule in overrides:
            if fnmatch.fnmatchcase(path, rule.pattern):
                return rule.boundary
    return default_boundary_for_path(path)
