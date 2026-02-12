from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from repo_routing.paths import repo_db_path


def _dt_sql(dt: datetime) -> str:
    return dt.replace(tzinfo=None).isoformat(sep=" ")


def sample_pr_numbers_created_in_window(
    *,
    repo: str,
    data_dir: str | Path = "data",
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    limit: int | None = None,
) -> list[int]:
    """Stable sampling for v0: deterministic created_at window slice."""

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

        where = ["repo_id = ?", "created_at is not null"]
        params: list[object] = [repo_id]
        if start_at is not None:
            where.append("created_at >= ?")
            params.append(_dt_sql(start_at))
        if end_at is not None:
            where.append("created_at <= ?")
            params.append(_dt_sql(end_at))

        sql = (
            "select number from pull_requests where "
            + " and ".join(where)
            + " order by created_at asc, number asc"
        )
        if limit is not None:
            sql += " limit ?"
            params.append(int(limit))

        return [int(r["number"]) for r in conn.execute(sql, tuple(params))]
    finally:
        conn.close()
