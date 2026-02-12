from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from .models import UserActivityCount
from .reader import HistoryReader


def popularity_index(
    reader: HistoryReader,
    *,
    as_of: datetime,
    lookback_days: int = 180,
) -> list[UserActivityCount]:
    """Rank users by review/comment activity in a lookback window."""

    start = as_of - timedelta(days=lookback_days)
    counts = Counter(reader.iter_participants(start=start, end=as_of))
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [UserActivityCount(login=login, count=count) for login, count in ranked]
