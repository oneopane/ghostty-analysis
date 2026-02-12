from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from repo_routing.paths import repo_db_path


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


def cutoff_for_pr(
    *,
    repo: str,
    pr_number: int,
    data_dir: str | Path = "data",
    policy: str = "created_at",
) -> datetime:
    def parse_created_at_delta(s: str) -> timedelta | None:
        if not s.startswith("created_at+"):
            return None
        raw = s[len("created_at+") :].strip()
        if not raw:
            raise ValueError("missing delta for created_at+...")

        unit = raw[-1]
        n_str = raw[:-1] if unit in {"s", "m", "h", "d"} else raw
        if not n_str.isdigit():
            raise ValueError(f"invalid created_at delta: {raw!r}")
        n = int(n_str)
        if unit == "s":
            return timedelta(seconds=n)
        if unit == "m":
            return timedelta(minutes=n)
        if unit == "h":
            return timedelta(hours=n)
        if unit == "d":
            return timedelta(days=n)
        return timedelta(seconds=n)

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
            "select id, created_at from pull_requests where repo_id = ? and number = ?",
            (repo_id, pr_number),
        ).fetchone()
        if pr is None:
            raise KeyError(f"pr not found: {repo}#{pr_number}")
        created = _parse_dt(pr["created_at"])
        if created is None:
            raise RuntimeError(f"missing created_at for {repo}#{pr_number}")

        if policy == "created_at":
            return created

        delta = parse_created_at_delta(policy)
        if delta is not None:
            return created + delta

        if policy == "ready_for_review":
            pr_id = int(pr["id"])
            try:
                rr = conn.execute(
                    """
                    select min(e.occurred_at) as ready_at
                    from pull_request_draft_intervals di
                    join events e on e.id = di.start_event_id
                    where di.pull_request_id = ?
                      and di.is_draft = 0
                      and e.occurred_at is not null
                    """,
                    (pr_id,),
                ).fetchone()
            except sqlite3.OperationalError:
                return created

            ready = None if rr is None else _parse_dt(rr["ready_at"])
            return created if ready is None else ready

        raise ValueError(f"unsupported cutoff policy (v0): {policy}")
    finally:
        conn.close()
