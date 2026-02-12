from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from ..boundary.consumption.models import PRBoundaryFootprint
from ..history.models import PullRequestFile, PullRequestSnapshot, ReviewRequest


class PRGateFields(BaseModel):
    issue: str | None = None
    ai_disclosure: str | None = None
    provenance: str | None = None

    missing_issue: bool = False
    missing_ai_disclosure: bool = False
    missing_provenance: bool = False


class RecentActivityEvent(BaseModel):
    kind: str
    actor_login: str
    occurred_at: datetime


class PRInputBundle(BaseModel):
    repo: str
    pr_number: int
    cutoff: datetime

    snapshot: PullRequestSnapshot

    changed_files: list[PullRequestFile] = Field(default_factory=list)
    review_requests: list[ReviewRequest] = Field(default_factory=list)

    author_login: str | None = None
    title: str | None = None
    body: str | None = None

    gate_fields: PRGateFields = Field(default_factory=PRGateFields)

    file_boundaries: dict[str, list[str]] = Field(default_factory=dict)
    file_boundary_weights: dict[str, dict[str, float]] = Field(default_factory=dict)
    boundaries: list[str] = Field(default_factory=list)
    boundary_coverage: dict[str, object] = Field(default_factory=dict)
    boundary_strategy: str | None = None
    boundary_strategy_version: str | None = None

    # TODO(boundary-migration-pr04): remove legacy aliases once predictor stack is migrated.
    file_areas: dict[str, str] = Field(default_factory=dict)
    areas: list[str] = Field(default_factory=list)

    recent_activity: list[RecentActivityEvent] = Field(default_factory=list)
    repo_profile_path: str | None = None
    repo_profile_qa: dict[str, object] = Field(default_factory=dict)


class PRInputBuilderOptions(BaseModel):
    include_recent_activity: bool = False
    recent_activity_window: timedelta = timedelta(days=30)
    recent_activity_limit: int = 200

    boundary_strategy_id: str = "hybrid_path_cochange.v1"
    boundary_required: bool = False
