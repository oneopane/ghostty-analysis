from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from ..time import require_dt_utc
from .artifacts import BoundaryModelArtifact
from .inference import BoundaryInferenceContext, get_boundary_strategy
from .io import write_boundary_artifact
from .models import BoundaryModel, MembershipMode


def build_boundary_model(
    *,
    repo_full_name: str,
    cutoff_utc: datetime,
    strategy_id: str = "hybrid_path_cochange.v1",
    data_dir: str | Path = "data",
    membership_mode: MembershipMode = MembershipMode.MIXED,
    strategy_config: dict[str, Any] | None = None,
) -> tuple[BoundaryModel, list[dict[str, Any]]]:
    strategy = get_boundary_strategy(strategy_id)
    context = BoundaryInferenceContext(
        repo_full_name=repo_full_name,
        cutoff_utc=require_dt_utc(cutoff_utc, name="cutoff_utc"),
        data_dir=data_dir,
        membership_mode=membership_mode,
        config=dict(strategy_config or {}),
    )
    return strategy.infer(context)


def write_boundary_model_artifacts(
    *,
    repo_full_name: str,
    cutoff_utc: datetime,
    cutoff_key: str,
    strategy_id: str = "hybrid_path_cochange.v1",
    data_dir: str | Path = "data",
    membership_mode: MembershipMode = MembershipMode.MIXED,
    strategy_config: dict[str, Any] | None = None,
    manifest_metadata: dict[str, Any] | None = None,
) -> BoundaryModelArtifact:
    model, signal_rows = build_boundary_model(
        repo_full_name=repo_full_name,
        cutoff_utc=cutoff_utc,
        strategy_id=strategy_id,
        data_dir=data_dir,
        membership_mode=membership_mode,
        strategy_config=strategy_config,
    )
    return write_boundary_artifact(
        model=model,
        repo_full_name=repo_full_name,
        data_dir=data_dir,
        cutoff_key=cutoff_key,
        signal_rows=signal_rows,
        manifest_metadata=manifest_metadata,
    )
