from __future__ import annotations

from datetime import timedelta

from pydantic import BaseModel, Field


class EvalDefaults(BaseModel):
    """Pinned v0 defaults."""

    strict_streaming_eval: bool = True
    cutoff_policy: str = "created_at"

    intent_truth_window: timedelta = timedelta(minutes=60)
    behavior_truth_policy: str = "first_non_author_non_bot_review"

    exclude_bots: bool = True
    exclude_author: bool = True

    candidate_pool_lookback_days: int = 180

    top_k: int = 5
    hit_ks: tuple[int, ...] = (1, 3, 5)


class EvalRunConfig(BaseModel):
    repo: str
    data_dir: str = "data"
    run_id: str

    defaults: EvalDefaults = Field(default_factory=EvalDefaults)
