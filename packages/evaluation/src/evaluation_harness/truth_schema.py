from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class TruthResultStatus(StrEnum):
    observed = "observed"
    no_post_cutoff_response = "no_post_cutoff_response"
    unknown_due_to_ingestion_gap = "unknown_due_to_ingestion_gap"
    policy_unavailable = "policy_unavailable"


class TruthResultDiagnostics(BaseModel):
    window_start: datetime
    window_end: datetime
    source_branch: str | None = None
    scanned_review_rows: int = 0
    scanned_review_comment_rows: int = 0
    eligible_candidates: int = 0
    data_gaps: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class TruthResultProvenance(BaseModel):
    policy_hash: str
    engine_version: str = "truth_engine.v1"


class TruthResult(BaseModel):
    policy_id: str
    policy_version: str
    status: TruthResultStatus
    targets: list[str] = Field(default_factory=list)
    diagnostics: TruthResultDiagnostics
    provenance: TruthResultProvenance
