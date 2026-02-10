from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .areas.basis import (
    UserAreaMatrix,
    build_user_area_activity_frame,
    build_user_area_activity_rows,
    rows_to_user_area_matrix,
)
from .config import AreaMembershipConfig


def build_area_membership_dataset(
    *,
    repo: str,
    cutoff: datetime,
    data_dir: str | Path = "data",
    config: AreaMembershipConfig | None = None,
    as_polars: bool = True,
):
    """Notebook-first API for mixed-membership dataset construction.

    - `as_polars=True`: returns Polars DataFrame (if available)
    - `as_polars=False`: returns deterministic rows list
    """

    return build_user_area_activity_frame(
        repo=repo,
        cutoff=cutoff,
        data_dir=data_dir,
        config=config,
        engine="polars" if as_polars else "rows",
    )


def build_area_membership_matrix(
    *,
    repo: str,
    cutoff: datetime,
    data_dir: str | Path = "data",
    config: AreaMembershipConfig | None = None,
) -> UserAreaMatrix:
    rows = build_user_area_activity_rows(
        repo=repo,
        cutoff=cutoff,
        data_dir=data_dir,
        config=config,
    )
    cfg = config or AreaMembershipConfig()
    return rows_to_user_area_matrix(rows, min_user_total_weight=cfg.min_user_total_weight)
