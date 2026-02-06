from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .config import EvalRunConfig


class EvalManifest(BaseModel):
    kind: str = "eval_manifest"
    version: str = "v0"

    repo: str
    run_id: str
    generated_at: datetime

    db_max_event_occurred_at: datetime | None = None
    db_max_watermark_updated_at: datetime | None = None
    package_versions: dict[str, str | None] = Field(default_factory=dict)
    routers: list[dict[str, Any]] = Field(default_factory=list)
    baselines: list[str] = Field(default_factory=list)

    config: dict[str, Any]
    pr_numbers: list[int] = Field(default_factory=list)


def build_manifest(
    *,
    cfg: EvalRunConfig,
    pr_numbers: list[int],
    generated_at: datetime,
    db_max_event_occurred_at: datetime | None = None,
    db_max_watermark_updated_at: datetime | None = None,
    package_versions: dict[str, str | None] | None = None,
    baselines: list[str] | None = None,
    routers: list[dict[str, Any]] | None = None,
) -> EvalManifest:
    return EvalManifest(
        repo=cfg.repo,
        run_id=cfg.run_id,
        generated_at=generated_at,
        db_max_event_occurred_at=db_max_event_occurred_at,
        db_max_watermark_updated_at=db_max_watermark_updated_at,
        package_versions=package_versions or {},
        routers=list(routers or []),
        baselines=list(baselines or []),
        config=cfg.model_dump(mode="json"),
        pr_numbers=list(pr_numbers),
    )
