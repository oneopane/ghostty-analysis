from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PullRequestFile(BaseModel):
    path: str
    status: str | None = None
    additions: int | None = None
    deletions: int | None = None
    changes: int | None = None


class ReviewRequest(BaseModel):
    reviewer_type: Literal["user", "team"]
    reviewer: str


class PullRequestSnapshot(BaseModel):
    repo: str
    number: int
    pull_request_id: int
    issue_id: int | None = None

    author_login: str | None = None
    created_at: datetime | None = None

    title: str | None = None
    body: str | None = None

    base_ref: str | None = None
    base_sha: str | None = None
    head_sha: str | None = None

    # Optional process metadata. Reader currently leaves these empty unless available.
    labels: list[str] = Field(default_factory=list)
    assignees: list[str] = Field(default_factory=list)
    milestone_present: bool | None = None

    changed_files: list[PullRequestFile] = Field(default_factory=list)
    review_requests: list[ReviewRequest] = Field(default_factory=list)


class UserActivityCount(BaseModel):
    login: str
    count: int
