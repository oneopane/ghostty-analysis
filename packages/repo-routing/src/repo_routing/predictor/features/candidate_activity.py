from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ...inputs.models import PRInputBundle
from .sql import candidate_last_activity_and_counts, connect_repo_db


def days_since_last_candidate_activity(
    *,
    repo: str,
    candidate_login: str,
    cutoff: datetime,
    data_dir: str | Path,
) -> float | None:
    conn = connect_repo_db(repo=repo, data_dir=data_dir)
    try:
        row = conn.execute("select id from repos where full_name = ?", (repo,)).fetchone()
        if row is None:
            raise KeyError(f"repo not found in db: {repo}")
        repo_id = int(row["id"])

        last_ts, _counts = candidate_last_activity_and_counts(
            conn=conn,
            repo_id=repo_id,
            candidate_login=candidate_login,
            cutoff=cutoff,
            windows_days=(30,),
        )
    finally:
        conn.close()

    if last_ts is None:
        return None
    return (cutoff - last_ts).total_seconds() / 86400.0


def candidate_event_volume_by_windows(
    *,
    repo: str,
    candidate_login: str,
    cutoff: datetime,
    windows_days: tuple[int, ...],
    data_dir: str | Path,
) -> dict[int, int]:
    conn = connect_repo_db(repo=repo, data_dir=data_dir)
    try:
        row = conn.execute("select id from repos where full_name = ?", (repo,)).fetchone()
        if row is None:
            raise KeyError(f"repo not found in db: {repo}")
        repo_id = int(row["id"])

        _last_ts, counts = candidate_last_activity_and_counts(
            conn=conn,
            repo_id=repo_id,
            candidate_login=candidate_login,
            cutoff=cutoff,
            windows_days=windows_days,
        )
        return counts
    finally:
        conn.close()


def build_candidate_activity_features(
    *,
    input: PRInputBundle,
    candidate_login: str,
    data_dir: str | Path,
    windows_days: tuple[int, ...] = (30, 90, 180),
) -> dict[str, int | float | bool]:
    days_since = days_since_last_candidate_activity(
        repo=input.repo,
        candidate_login=candidate_login,
        cutoff=input.cutoff,
        data_dir=data_dir,
    )
    counts = candidate_event_volume_by_windows(
        repo=input.repo,
        candidate_login=candidate_login,
        cutoff=input.cutoff,
        windows_days=windows_days,
        data_dir=data_dir,
    )

    out: dict[str, int | float | bool] = {
        "cand.activity.days_since_last_event": days_since,
        "cand.activity.has_prior_event": days_since is not None,
    }
    for days in sorted(counts):
        out[f"cand.activity.events_{days}d"] = int(counts[days])
    return out


def build_candidate_activity_table(
    *,
    input: PRInputBundle,
    candidate_logins: list[str],
    data_dir: str | Path,
    windows_days: tuple[int, ...] = (30, 90, 180),
) -> dict[str, dict[str, int | float | bool]]:
    out: dict[str, dict[str, int | float | bool]] = {}
    for login in sorted(set(candidate_logins), key=lambda s: s.lower()):
        out[login] = build_candidate_activity_features(
            input=input,
            candidate_login=login,
            data_dir=data_dir,
            windows_days=windows_days,
        )
    return out
