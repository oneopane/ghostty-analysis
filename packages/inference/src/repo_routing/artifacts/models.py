from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ..history.models import PullRequestFile, ReviewRequest
from ..router.base import RouteResult


class PRSnapshotArtifact(BaseModel):
    kind: str = "pr_snapshot"
    version: str = "v0"

    repo: str
    pr_number: int
    as_of: datetime

    author: str | None = None
    title: str | None = None
    body: str | None = None
    base_sha: str | None = None
    head_sha: str | None = None

    changed_files: list[PullRequestFile] = Field(default_factory=list)
    review_requests: list[ReviewRequest] = Field(default_factory=list)


class RouteArtifact(BaseModel):
    kind: str = "route_result"
    version: str = "v1"

    router_id: str
    result: RouteResult
    meta: dict[str, object] = Field(default_factory=dict)
