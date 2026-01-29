from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ..models import GateCorrelationSummary, QueueSummary, RoutingAgreementSummary


class EvalReport(BaseModel):
    kind: str = "eval_report"
    version: str = "v0"

    repo: str
    run_id: str
    generated_at: datetime

    db_max_event_occurred_at: datetime | None = None
    db_max_watermark_updated_at: datetime | None = None
    package_versions: dict[str, str | None] = Field(default_factory=dict)

    baselines: list[str] = Field(default_factory=list)

    routing_agreement: dict[str, RoutingAgreementSummary] = Field(default_factory=dict)
    gates: GateCorrelationSummary | None = None
    queue: dict[str, QueueSummary] = Field(default_factory=dict)

    notes: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)
