from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .paths import repo_db_path


def _dt_sql(dt: datetime) -> str:
    return dt.replace(tzinfo=None).isoformat(sep=" ")


def _parse_dt(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    s = str(value)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class RepoDb:
    repo: str
    data_dir: str | Path = "data"

    def connect(self) -> sqlite3.Connection:
        p = repo_db_path(repo_full_name=self.repo, data_dir=self.data_dir)
        conn = sqlite3.connect(str(p))
        conn.row_factory = sqlite3.Row
        return conn

    def repo_id(self, conn: sqlite3.Connection) -> int:
        row = conn.execute(
            "select id from repos where full_name = ?", (self.repo,)
        ).fetchone()
        if row is None:
            raise KeyError(f"repo not found in db: {self.repo}")
        return int(row["id"])

    def pr_ids(
        self, conn: sqlite3.Connection, *, pr_number: int
    ) -> tuple[int, int | None]:
        repo_id = self.repo_id(conn)
        pr = conn.execute(
            "select id, user_id from pull_requests where repo_id = ? and number = ?",
            (repo_id, pr_number),
        ).fetchone()
        if pr is None:
            raise KeyError(f"pr not found: {self.repo}#{pr_number}")
        return int(pr["id"]), pr["user_id"]

    def is_merged_as_of(
        self, conn: sqlite3.Connection, *, pr_id: int, cutoff: datetime
    ) -> bool:
        # We prefer events because pull_requests.merged_at is a mutable snapshot.
        cutoff_s = _dt_sql(cutoff)

        merged = conn.execute(
            """
            select 1
            from events e
            where e.subject_type = 'pull_request'
              and e.subject_id = ?
              and e.event_type = 'pull_request.merged'
              and e.occurred_at is not null
              and e.occurred_at <= ?
            limit 1
            """,
            (pr_id, cutoff_s),
        ).fetchone()
        return merged is not None

    def max_event_occurred_at(self, conn: sqlite3.Connection) -> datetime | None:
        repo_id = self.repo_id(conn)
        row = conn.execute(
            "select max(occurred_at) as max_at from events where repo_id = ?",
            (repo_id,),
        ).fetchone()
        if row is None:
            return None
        return _parse_dt(row["max_at"])

    def max_watermark_updated_at(self, conn: sqlite3.Connection) -> datetime | None:
        repo_id = self.repo_id(conn)
        try:
            row = conn.execute(
                "select max(updated_at) as max_at from watermarks where repo_id = ?",
                (repo_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            # Some synthetic/minimal fixtures may not include optional tables.
            return None
        if row is None:
            return None
        return _parse_dt(row["max_at"])
