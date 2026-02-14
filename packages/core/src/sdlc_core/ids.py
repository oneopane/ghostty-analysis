from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from .hashing import stable_hash_json


@dataclass(frozen=True)
class RunId:
    value: str


def compute_run_id(
    *,
    config_payload: Mapping[str, Any],
    now: datetime | None = None,
    hash_len: int = 12,
) -> str:
    ts = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    digest = stable_hash_json(dict(config_payload))[:hash_len]
    return f"{ts}-{digest}"
