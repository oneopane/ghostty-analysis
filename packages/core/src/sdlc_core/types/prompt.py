from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class PromptSpec(BaseModel):
    prompt_id: str
    prompt_version: str
    template: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


class PromptRef(BaseModel):
    prompt_id: str
    prompt_version: str
    prompt_hash: str
    schema_version: str = "v1"
