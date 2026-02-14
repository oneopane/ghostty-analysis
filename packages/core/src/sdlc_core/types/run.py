from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RunMetadata(BaseModel):
    run_id: str
    run_kind: str
    generated_at: datetime
    repo: str | None = None
    inputs_hash: str | None = None
    config_hash: str | None = None


class RunManifest(BaseModel):
    run_id: str
    run_kind: str
    generated_at: datetime
    repo: str
    task_id: str
    routers: list[str] = Field(default_factory=list)
    produced_artifact_refs: list[str] = Field(default_factory=list)
    db_max_event_occurred_at: str | None = None
    db_max_watermark_updated_at: str | None = None
    llm_usage: dict[str, object] = Field(default_factory=dict)
    config_hash: str | None = None
    code_version: str | None = None
