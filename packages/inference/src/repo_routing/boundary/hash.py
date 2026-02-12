from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .config import BoundaryHashConfig
from .models import BoundaryModel


def _round_float(value: float, *, ndigits: int) -> float:
    return round(float(value), ndigits)


def _normalize(value: Any, *, ndigits: int) -> Any:
    if isinstance(value, float):
        return _round_float(value, ndigits=ndigits)
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {k: _normalize(v, ndigits=ndigits) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [_normalize(v, ndigits=ndigits) for v in value]
    return value


def canonical_boundary_payload(
    model: BoundaryModel, *, hash_config: BoundaryHashConfig | None = None
) -> dict[str, Any]:
    cfg = hash_config or BoundaryHashConfig()

    units = sorted(
        (u.model_dump(mode="json") for u in model.units),
        key=lambda u: (
            str(u.get("granularity", "")),
            str(u.get("unit_id", "")),
            str(u.get("path", "") or ""),
            str(u.get("symbol", "") or ""),
            str(u.get("function", "") or ""),
        ),
    )
    boundaries = sorted(
        (b.model_dump(mode="json") for b in model.boundaries),
        key=lambda b: (
            str(b.get("granularity", "")),
            str(b.get("boundary_id", "")),
            str(b.get("name", "")),
        ),
    )
    memberships = sorted(
        (m.model_dump(mode="json") for m in model.memberships),
        key=lambda m: (
            str(m.get("unit_id", "")),
            str(m.get("boundary_id", "")),
            float(m.get("weight", 0.0)),
        ),
    )

    payload = {
        "schema_version": model.schema_version,
        "strategy_id": model.strategy_id,
        "strategy_version": model.strategy_version,
        "repo": model.repo,
        "cutoff_utc": model.cutoff_utc,
        "membership_mode": model.membership_mode.value,
        "units": units,
        "boundaries": boundaries,
        "memberships": memberships,
        "metadata": model.metadata,
    }
    return _normalize(payload, ndigits=cfg.float_round_decimals)


def boundary_model_hash(
    model: BoundaryModel, *, hash_config: BoundaryHashConfig | None = None
) -> str:
    cfg = hash_config or BoundaryHashConfig()
    payload = canonical_boundary_payload(model, hash_config=cfg)
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    if cfg.algorithm != "sha256":
        raise ValueError(f"unsupported boundary hash algorithm: {cfg.algorithm}")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
