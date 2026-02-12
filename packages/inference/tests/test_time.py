from __future__ import annotations

from datetime import datetime, timezone

from repo_routing.time import dt_sql_utc, parse_dt_utc


def test_parse_dt_utc_naive_string_assumes_utc() -> None:
    dt = parse_dt_utc("2024-01-02T03:04:05")
    assert dt is not None
    assert dt.tzinfo == timezone.utc
    assert dt.isoformat() == "2024-01-02T03:04:05+00:00"


def test_parse_dt_utc_normalizes_offset_to_utc() -> None:
    dt = parse_dt_utc("2024-01-02T03:04:05+02:00")
    assert dt is not None
    assert dt.tzinfo == timezone.utc
    assert dt.isoformat() == "2024-01-02T01:04:05+00:00"


def test_dt_sql_utc_strips_timezone_for_sql_text_comparison() -> None:
    raw = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    assert dt_sql_utc(raw) == "2024-01-02 03:04:05"
