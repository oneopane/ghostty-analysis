from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CandidatePoolConfig(BaseModel):
    lookback_days: int = 180
    exclude_author: bool = True
    exclude_bots: bool = True


class DecayConfig(BaseModel):
    half_life_days: float = 30.0
    lookback_days: int = 180

    @field_validator("half_life_days")
    @classmethod
    def _positive_half_life(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("half_life_days must be > 0")
        return value

    @field_validator("lookback_days")
    @classmethod
    def _positive_lookback(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("lookback_days must be > 0")
        return value


class EventWeights(BaseModel):
    review_submitted: float = 1.0
    review_comment_created: float = 0.4
    comment_created: float = 0.2


class FeatureWeights(BaseModel):
    boundary_overlap_activity: float = 1.0
    activity_total: float = 0.2


class FiltersConfig(BaseModel):
    min_activity_total: float = 0.0


class ThresholdsConfig(BaseModel):
    confidence_high_margin: float
    confidence_med_margin: float


class LabelsConfig(BaseModel):
    include_boundary_labels: bool = False


class ScoringConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    feature_version: str

    candidate_pool: CandidatePoolConfig = Field(default_factory=CandidatePoolConfig)
    decay: DecayConfig = Field(default_factory=DecayConfig)
    event_weights: EventWeights = Field(default_factory=EventWeights)
    weights: FeatureWeights
    filters: FiltersConfig = Field(default_factory=FiltersConfig)
    thresholds: ThresholdsConfig
    labels: LabelsConfig = Field(default_factory=LabelsConfig)


def load_scoring_config(path: str | Path) -> ScoringConfig:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    return ScoringConfig.model_validate(data)
