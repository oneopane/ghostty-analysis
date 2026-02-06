from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ...inputs.models import PRInputBundle


def days_since_last_candidate_activity(
    *,
    repo: str,
    candidate_login: str,
    cutoff: datetime,
    data_dir: str | Path,
) -> float | None:
    """Feature #49: candidate activity recency in days.

    SQL derivation:
    - Find latest review/comment event by candidate in repo with timestamp <= cutoff.
    - Convert `cutoff - latest_ts` to days.
    """
    raise NotImplementedError


def candidate_event_volume_by_windows(
    *,
    repo: str,
    candidate_login: str,
    cutoff: datetime,
    windows_days: tuple[int, ...],
    data_dir: str | Path,
) -> dict[int, int]:
    """Feature #50: candidate event counts for 30/90/180d windows.

    SQL derivation:
    - Count review/comment rows in repo where candidate is actor and
      timestamp in [cutoff-window, cutoff].
    - Optionally apply deterministic decay downstream in ranker.
    """
    raise NotImplementedError


def build_candidate_activity_features(
    *,
    input: PRInputBundle,
    candidate_login: str,
    data_dir: str | Path,
    windows_days: tuple[int, ...] = (30, 90, 180),
) -> dict[str, int | float | bool]:
    """Assemble candidate activity family features (#49-#50).

    Returns flat deterministic keys under `cand.activity.*` for one candidate.
    """
    raise NotImplementedError


def build_candidate_activity_table(
    *,
    input: PRInputBundle,
    candidate_logins: list[str],
    data_dir: str | Path,
    windows_days: tuple[int, ...] = (30, 90, 180),
) -> dict[str, dict[str, int | float | bool]]:
    """Batch candidate feature builder for ranker input.

    High-level implementation plan:
    - iterate sorted candidate logins for deterministic ordering
    - compute per-candidate features via `build_candidate_activity_features`
    """
    raise NotImplementedError
