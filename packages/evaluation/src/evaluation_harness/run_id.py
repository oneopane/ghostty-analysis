from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from .config import EvalRunConfig


def _stable_config_bytes(cfg: EvalRunConfig) -> bytes:
    # run_id must not be part of the hash.
    d = cfg.model_dump(mode="json")
    d.pop("run_id", None)
    data = json.dumps(d, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return data.encode("utf-8")


def compute_run_id(*, cfg: EvalRunConfig, now: datetime | None = None) -> str:
    ts = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    h = hashlib.sha256(_stable_config_bytes(cfg)).hexdigest()[:12]
    return f"{ts}-{h}"
