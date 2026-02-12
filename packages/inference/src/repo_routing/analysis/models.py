from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ..parsing.gates import GateFields
from ..router.base import Evidence


class CandidateFeatures(BaseModel):
    activity_total: float = 0.0
    boundary_overlap_activity: float = 0.0


class CandidateAnalysis(BaseModel):
    login: str
    score: float
    features: CandidateFeatures
    evidence: list[Evidence] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    repo: str
    pr_number: int
    cutoff: datetime

    author_login: str | None = None
    boundaries: list[str] = Field(default_factory=list)
    gates: GateFields

    candidates: list[CandidateAnalysis] = Field(default_factory=list)

    confidence: str = "unknown"
    risk: str = "unknown"
    notes: list[str] = Field(default_factory=list)

    config_version: str | None = None
    feature_version: str | None = None
