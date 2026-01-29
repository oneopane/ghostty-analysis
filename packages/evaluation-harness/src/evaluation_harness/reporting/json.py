from __future__ import annotations

from dataclasses import asdict
from typing import Any

from pydantic import BaseModel


def to_json_dict(obj: object) -> dict[str, Any]:
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)  # type: ignore[arg-type]
    if isinstance(obj, dict):
        return obj
    raise TypeError(f"unsupported json type: {type(obj)!r}")
