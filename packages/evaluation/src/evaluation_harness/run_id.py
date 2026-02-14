from __future__ import annotations

from datetime import datetime

from sdlc_core.ids import compute_run_id as compute_core_run_id

from .config import EvalRunConfig


def compute_run_id(*, cfg: EvalRunConfig, now: datetime | None = None) -> str:
    # run_id must not be part of the hash.
    payload = cfg.model_dump(mode="json")
    payload.pop("run_id", None)
    return compute_core_run_id(config_payload=payload, now=now, hash_len=12)
