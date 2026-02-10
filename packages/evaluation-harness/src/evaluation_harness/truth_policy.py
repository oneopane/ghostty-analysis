from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TruthTargetKind(StrEnum):
    actor_set = "actor_set"


class TruthSelector(StrEnum):
    first = "first"
    last = "last"
    union = "union"
    priority_chain = "priority_chain"


class TruthSource(StrEnum):
    reviews = "reviews"
    review_comments = "review_comments"
    events = "events"
    review_requests = "review_requests"


class TruthPolicySpec(BaseModel):
    id: str
    version: str = "v1"
    target_kind: TruthTargetKind = TruthTargetKind.actor_set
    window_seconds: int = 3600
    sources: list[TruthSource] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    selector: TruthSelector = TruthSelector.first
    status_rules: list[dict[str, Any]] = Field(default_factory=list)
    fallback_chain: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        out = value.strip()
        if not out:
            raise ValueError("policy id is required")
        if not re.fullmatch(r"[a-z0-9_]+", out):
            raise ValueError("policy id must match [a-z0-9_]+")
        return out

    @field_validator("window_seconds")
    @classmethod
    def _validate_window(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("window_seconds must be > 0")
        return value

    def stable_hash(self) -> str:
        payload = self.model_dump(mode="json")
        data = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        return hashlib.sha256(data.encode("utf-8")).hexdigest()


def builtin_truth_policy_specs() -> dict[str, TruthPolicySpec]:
    """Narrow v1 built-ins used by evaluation-harness truth contracts."""
    specs = [
        TruthPolicySpec(
            id="first_response_v1",
            window_seconds=3600,
            sources=[TruthSource.reviews, TruthSource.review_comments],
            filters={"exclude_bots": True, "exclude_author": True},
            selector=TruthSelector.first,
            status_rules=[
                {"if": "target_found", "status": "observed"},
                {"if": "coverage_complete", "status": "no_post_cutoff_response"},
                {"if": "default", "status": "unknown_due_to_ingestion_gap"},
            ],
        ),
        TruthPolicySpec(
            id="first_approval_v1",
            window_seconds=3600,
            sources=[TruthSource.reviews],
            filters={
                "exclude_bots": True,
                "exclude_author": True,
                "review_states": ["APPROVED"],
            },
            selector=TruthSelector.first,
            status_rules=[
                {"if": "target_found", "status": "observed"},
                {"if": "coverage_complete", "status": "no_post_cutoff_response"},
                {"if": "default", "status": "unknown_due_to_ingestion_gap"},
            ],
        ),
        TruthPolicySpec(
            id="merger_v1",
            window_seconds=48 * 3600,
            sources=[TruthSource.events],
            filters={"event_types": ["pull_request.merged"]},
            selector=TruthSelector.first,
            status_rules=[
                {"if": "target_found", "status": "observed"},
                {"if": "policy_not_ready", "status": "policy_unavailable"},
                {"if": "default", "status": "no_post_cutoff_response"},
            ],
        ),
        TruthPolicySpec(
            id="hybrid_owner_v1",
            window_seconds=48 * 3600,
            sources=[TruthSource.reviews, TruthSource.events, TruthSource.review_requests],
            filters={"exclude_bots": True, "exclude_author": True},
            selector=TruthSelector.priority_chain,
            status_rules=[
                {"if": "approval_branch", "status": "observed"},
                {"if": "merger_branch", "status": "observed"},
                {"if": "request_branch", "status": "observed"},
                {"if": "coverage_complete", "status": "no_post_cutoff_response"},
                {"if": "default", "status": "unknown_due_to_ingestion_gap"},
            ],
            fallback_chain=["first_approval_v1", "merger_v1", "first_response_v1"],
        ),
    ]
    return {spec.id: spec for spec in specs}
