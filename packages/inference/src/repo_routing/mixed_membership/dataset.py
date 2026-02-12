from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .boundaries.basis import (
    UserBoundaryMatrix,
    build_user_boundary_activity_frame,
    build_user_boundary_activity_rows,
    rows_to_user_boundary_matrix,
)
from .config import BoundaryMembershipConfig


def build_boundary_membership_dataset(
    *,
    repo: str,
    cutoff: datetime,
    data_dir: str | Path = "data",
    config: BoundaryMembershipConfig | None = None,
    as_polars: bool = True,
):
    return build_user_boundary_activity_frame(
        repo=repo,
        cutoff=cutoff,
        data_dir=data_dir,
        config=config,
        engine="polars" if as_polars else "rows",
    )


def build_boundary_membership_matrix(
    *,
    repo: str,
    cutoff: datetime,
    data_dir: str | Path = "data",
    config: BoundaryMembershipConfig | None = None,
) -> UserBoundaryMatrix:
    rows = build_user_boundary_activity_rows(
        repo=repo,
        cutoff=cutoff,
        data_dir=data_dir,
        config=config,
    )
    cfg = config or BoundaryMembershipConfig()
    return rows_to_user_boundary_matrix(rows, min_user_total_weight=cfg.min_user_total_weight)
