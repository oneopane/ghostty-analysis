from __future__ import annotations

from pathlib import Path


def repo_db_path(*, repo_full_name: str, data_dir: str | Path) -> Path:
    owner, repo = repo_full_name.split("/", 1)
    base = Path(data_dir)
    return base / "github" / owner / repo / "history.sqlite"


def repo_eval_run_dir(
    *, repo_full_name: str, data_dir: str | Path, run_id: str
) -> Path:
    owner, repo = repo_full_name.split("/", 1)
    base = Path(data_dir)
    return base / "github" / owner / repo / "eval" / run_id
