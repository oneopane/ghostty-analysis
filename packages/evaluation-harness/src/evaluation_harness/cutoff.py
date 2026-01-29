from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from repo_routing.paths import repo_db_path


def _parse_dt(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def cutoff_for_pr(
    *,
    repo: str,
    pr_number: int,
    data_dir: str | Path = "data",
    policy: str = "created_at",
) -> datetime:
    if policy != "created_at":
        raise ValueError(f"unsupported cutoff policy (v0): {policy}")

    db = repo_db_path(repo_full_name=repo, data_dir=data_dir)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "select id from repos where full_name = ?", (repo,)
        ).fetchone()
        if row is None:
            raise KeyError(f"repo not found in db: {repo}")
        repo_id = int(row["id"])

        pr = conn.execute(
            "select created_at from pull_requests where repo_id = ? and number = ?",
            (repo_id, pr_number),
        ).fetchone()
        if pr is None:
            raise KeyError(f"pr not found: {repo}#{pr_number}")
        created = _parse_dt(pr["created_at"])
        if created is None:
            raise RuntimeError(f"missing created_at for {repo}#{pr_number}")
        return created
    finally:
        conn.close()
