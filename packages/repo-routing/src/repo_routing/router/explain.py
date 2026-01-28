from __future__ import annotations

import json

from .base import RouteResult


def result_json(result: RouteResult) -> str:
    """Serialize a RouteResult deterministically."""
    return json.dumps(result.model_dump(mode="json"), sort_keys=True)
