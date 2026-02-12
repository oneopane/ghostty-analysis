from __future__ import annotations

from pathlib import Path


def resolve_snapshot_root(*, configured_root: str | Path | None) -> Path | None:
    if configured_root is None:
        return None
    root = Path(configured_root)
    if not root.exists() or not root.is_dir():
        return None
    return root
