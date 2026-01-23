from __future__ import annotations

from datetime import datetime, timezone


def parse_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        text = value.replace("Z", "+00:00")
        return datetime.fromisoformat(text)
    raise ValueError(f"Unsupported datetime value: {value!r}")
