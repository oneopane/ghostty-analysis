from __future__ import annotations

from datetime import datetime, timezone


def parse_dt_utc(value: object) -> datetime | None:
    """Parse datetime-like values into timezone-aware UTC datetimes.

    - ``None`` -> ``None``
    - ``datetime`` -> normalized to UTC (naive values are treated as UTC)
    - ``str``/other -> parsed with ``datetime.fromisoformat`` after ``Z`` normalization
    """

    if value is None:
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def require_dt_utc(value: object, *, name: str = "datetime") -> datetime:
    dt = parse_dt_utc(value)
    if dt is None:
        raise ValueError(f"{name} is required")
    return dt


def dt_sql_utc(dt: datetime, *, timespec: str | None = None) -> str:
    """Serialize a UTC datetime for SQLite TEXT comparisons.

    Values are normalized to UTC then converted to naive strings to match the
    existing ingestion storage convention.
    """

    normalized = require_dt_utc(dt)
    naive = normalized.replace(tzinfo=None)
    if timespec is None:
        return naive.isoformat(sep=" ")
    return naive.isoformat(sep=" ", timespec=timespec)
