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
    router_feature_meta: dict[str, dict[str, Any]] = Field(default_factory=dict)

    cutoff_source: str = "policy"
    pr_cutoffs: dict[str, str] = Field(default_factory=dict)
    truth: dict[str, Any] = Field(default_factory=dict)

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
    router_feature_meta: dict[str, dict[str, Any]] | None = None,
    cutoff_source: str = "policy",
    pr_cutoffs: dict[str, str] | None = None,
    truth: dict[str, Any] | None = None,
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
        router_feature_meta=dict(router_feature_meta or {}),
        cutoff_source=cutoff_source,
        pr_cutoffs=dict(pr_cutoffs or {}),
        truth=dict(truth or {}),
        config=cfg.model_dump(mode="json"),
        pr_numbers=list(pr_numbers),
    )
