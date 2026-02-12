from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class Granularity(str, Enum):
    REPO = "repo"
    DIR = "dir"
    FILE = "file"
    SYMBOL = "symbol"
    FUNCTION = "function"


class MembershipMode(str, Enum):
    HARD = "hard"
    OVERLAP = "overlap"
    MIXED = "mixed"


class BoundaryUnit(BaseModel):
    unit_id: str
    granularity: Granularity
    path: str | None = None
    symbol: str | None = None
    function: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BoundaryDef(BaseModel):
    boundary_id: str
    name: str
    granularity: Granularity
    metadata: dict[str, Any] = Field(default_factory=dict)


class Membership(BaseModel):
    unit_id: str
    boundary_id: str
    weight: float = 1.0


class BoundaryModel(BaseModel):
    schema_version: str = "boundary_model.v1"

    strategy_id: str
    strategy_version: str

    repo: str
    cutoff_utc: datetime

    membership_mode: MembershipMode

    units: list[BoundaryUnit] = Field(default_factory=list)
    boundaries: list[BoundaryDef] = Field(default_factory=list)
    memberships: list[Membership] = Field(default_factory=list)

    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_membership_invariants(self) -> "BoundaryModel":
        unit_ids = [u.unit_id for u in self.units]
        boundary_ids = [b.boundary_id for b in self.boundaries]

        if len(unit_ids) != len(set(unit_ids)):
            raise ValueError("units contain duplicate unit_id values")
        if len(boundary_ids) != len(set(boundary_ids)):
            raise ValueError("boundaries contain duplicate boundary_id values")

        unit_set = set(unit_ids)
        boundary_set = set(boundary_ids)
        by_unit: dict[str, list[Membership]] = {u: [] for u in unit_ids}

        for m in self.memberships:
            if m.unit_id not in unit_set:
                raise ValueError(f"membership references unknown unit_id: {m.unit_id}")
            if m.boundary_id not in boundary_set:
                raise ValueError(
                    f"membership references unknown boundary_id: {m.boundary_id}"
                )
            if m.weight <= 0:
                raise ValueError("membership weights must be positive")
            by_unit[m.unit_id].append(m)

        for unit_id, memberships in by_unit.items():
            if self.membership_mode == MembershipMode.HARD:
                if len(memberships) != 1:
                    raise ValueError(
                        f"hard mode requires exactly 1 membership for unit {unit_id}"
                    )
                if abs(memberships[0].weight - 1.0) > 1e-9:
                    raise ValueError("hard mode requires weight=1.0")
            elif self.membership_mode == MembershipMode.OVERLAP:
                if len(memberships) < 1:
                    raise ValueError(
                        f"overlap mode requires at least 1 membership for unit {unit_id}"
                    )
                if any(abs(m.weight - 1.0) > 1e-9 for m in memberships):
                    raise ValueError("overlap mode requires all weights to be 1.0")
            elif self.membership_mode == MembershipMode.MIXED:
                if len(memberships) < 1:
                    raise ValueError(
                        f"mixed mode requires at least 1 membership for unit {unit_id}"
                    )
                total = sum(m.weight for m in memberships)
                if abs(total - 1.0) > 1e-6:
                    raise ValueError(
                        f"mixed mode requires unit weights to sum to 1.0; got {total} for {unit_id}"
                    )

        return self
