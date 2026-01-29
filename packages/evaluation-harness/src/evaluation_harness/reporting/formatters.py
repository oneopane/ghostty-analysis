from __future__ import annotations

import json
from datetime import datetime


def json_dumps(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def json_dumps_compact(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=True) + "\n"


def iso(dt: datetime | None) -> str | None:
    return None if dt is None else dt.isoformat()
