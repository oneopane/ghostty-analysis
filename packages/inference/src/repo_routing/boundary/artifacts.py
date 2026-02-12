from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .models import BoundaryModel


class BoundaryManifest(BaseModel):
    kind: str = "boundary_model_manifest"
    version: str = "v1"

    schema_version: str
    strategy_id: str
    strategy_version: str

    repo: str
    cutoff_utc: datetime

    model_hash: str

    unit_count: int
    boundary_count: int
    membership_count: int

    metadata: dict[str, Any] = Field(default_factory=dict)


class BoundaryModelArtifact(BaseModel):
    model: BoundaryModel
    manifest: BoundaryManifest
    memberships_rows: list[dict[str, Any]] = Field(default_factory=list)
    signal_rows: list[dict[str, Any]] = Field(default_factory=list)
