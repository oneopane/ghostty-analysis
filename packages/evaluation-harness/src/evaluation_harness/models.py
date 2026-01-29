from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PRRef(BaseModel):
    repo: str
    pr_number: int


class PRCutoff(BaseModel):
    repo: str
    pr_number: int
    cutoff: datetime


class TruthLabel(BaseModel):
    repo: str
    pr_number: int
    cutoff: datetime

    # v0 supports multi-label but defaults to one.
    targets: list[str] = Field(default_factory=list)


class PRMetrics(BaseModel):
    repo: str
    pr_number: int
    cutoff: datetime

    hit_at_1: float | None = None
    hit_at_3: float | None = None
    hit_at_5: float | None = None
    mrr: float | None = None


class RoutingAgreementSummary(BaseModel):
    repo: str
    run_id: str

    n: int
    hit_at_1: float | None = None
    hit_at_3: float | None = None
    hit_at_5: float | None = None
    mrr: float | None = None
