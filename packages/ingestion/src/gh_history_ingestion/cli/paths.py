from __future__ import annotations

from pathlib import Path


def default_db_path(*, repo_full_name: str, data_dir: str | Path) -> Path:
    """Compute a stable per-repo SQLite database path.

    Layout:
      <data_dir>/github/<owner>/<repo>/history.sqlite
    """

    owner, repo = repo_full_name.split("/", 1)
    base = Path(data_dir)
    return base / "github" / owner / repo / "history.sqlite"
