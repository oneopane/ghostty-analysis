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


def resolve_window(
    start_at: datetime | str | None, end_at: datetime | str | None
) -> tuple[datetime | None, datetime | None]:
    start = parse_datetime(start_at) if start_at else None
    end = parse_datetime(end_at) if end_at else None
    if start and not end:
        end = datetime.now(timezone.utc)
    if start and end and start > end:
        raise ValueError("start_at must be <= end_at")
    return start, end


def in_window(value: datetime | str | None, start: datetime | None, end: datetime | None) -> bool:
    if start is None and end is None:
        return True
    if value is None:
        return True
    dt = parse_datetime(value)
    if start and dt < start:
        return False
    if end and dt > end:
        return False
    return True
