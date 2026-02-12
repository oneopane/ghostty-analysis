from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class LLMRerankItem(BaseModel):
    target_type: str
    target_name: str
    score: float
    evidence_refs: list[str] = Field(default_factory=list)

    @field_validator("evidence_refs")
    @classmethod
    def _validate_evidence_refs(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("evidence_refs is required")
        return value


class LLMRerankResponse(BaseModel):
    model: str
    items: list[LLMRerankItem] = Field(default_factory=list)
    latency_ms: float | None = None
    cost_usd: float | None = None
