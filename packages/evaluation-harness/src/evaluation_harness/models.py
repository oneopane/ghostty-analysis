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


class GateMetrics(BaseModel):
    repo: str
    pr_number: int
    cutoff: datetime

    merged: bool | None = None
    missing_issue: bool | None = None
    missing_ai_disclosure: bool | None = None
    missing_provenance: bool | None = None


class GateFieldCorrelation(BaseModel):
    n: int
    missing_n: int
    present_n: int
    missing_rate: float | None = None
    merged_rate_missing: float | None = None
    merged_rate_present: float | None = None


class GateCorrelationSummary(BaseModel):
    repo: str
    run_id: str

    n: int

    issue: GateFieldCorrelation | None = None
    ai_disclosure: GateFieldCorrelation | None = None
    provenance: GateFieldCorrelation | None = None


class QueueMetrics(BaseModel):
    repo: str
    pr_number: int
    cutoff: datetime

    ttfr_seconds: float | None = None
    ttfc_seconds: float | None = None

    risk: str | None = None
    baseline: str | None = None


class QueueRiskBucketSummary(BaseModel):
    n: int
    ttfr_seconds_mean: float | None = None
    ttfc_seconds_mean: float | None = None


class QueueSummary(BaseModel):
    repo: str
    run_id: str

    baseline: str

    n: int

    by_risk: dict[str, QueueRiskBucketSummary] = Field(default_factory=dict)


class RoutingAgreementSummary(BaseModel):
    repo: str
    run_id: str

    n: int
    hit_at_1: float | None = None
    hit_at_3: float | None = None
    hit_at_5: float | None = None
    mrr: float | None = None
