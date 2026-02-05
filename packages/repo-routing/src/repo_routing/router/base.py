from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, Field


class TargetType(StrEnum):
    user = "user"
    team = "team"


class Target(BaseModel):
    type: TargetType
    name: str


class Evidence(BaseModel):
    kind: str
    data: dict[str, Any] = Field(default_factory=dict)


class RouteCandidate(BaseModel):
    target: Target
    score: float
    evidence: list[Evidence] = Field(default_factory=list)


class RouteResult(BaseModel):
    repo: str
    pr_number: int
    as_of: datetime

    top_k: int = 5
    candidates: list[RouteCandidate] = Field(default_factory=list)

    risk: str = "unknown"
    confidence: str = "unknown"
    notes: list[str] = Field(default_factory=list)


class Router(Protocol):
    def route(
        self,
        *,
        repo: str,
        pr_number: int,
        as_of: datetime,
        data_dir: str = "data",
        top_k: int = 5,
    ) -> RouteResult: ...
