from __future__ import annotations

from pydantic import BaseModel, Field

from .models import MembershipMode


class BoundaryHashConfig(BaseModel):
    algorithm: str = "sha256"
    float_round_decimals: int = 8


class BoundaryDeterminismConfig(BaseModel):
    sort_units: bool = True
    sort_boundaries: bool = True
    sort_memberships: bool = True


class BoundaryConfig(BaseModel):
    schema_version: str = "boundary_model.v1"
    default_membership_mode: MembershipMode = MembershipMode.HARD

    hash: BoundaryHashConfig = Field(default_factory=BoundaryHashConfig)
    determinism: BoundaryDeterminismConfig = Field(default_factory=BoundaryDeterminismConfig)
