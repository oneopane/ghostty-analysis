from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class OperatorRole(StrEnum):
    extractor = "extractor"
    summarizer = "summarizer"
    router = "router"
    taxonomy_builder = "taxonomy_builder"
    aligner = "aligner"
    policy_elicitor = "policy_elicitor"
    synthesizer = "synthesizer"
    end_to_end_predictor = "end_to_end_predictor"


class OperatorSpec(BaseModel):
    operator_id: str
    role: OperatorRole
    task_id: str
    requires_cutoff_safe_inputs: bool = True
    cost_class: str = "cheap"
