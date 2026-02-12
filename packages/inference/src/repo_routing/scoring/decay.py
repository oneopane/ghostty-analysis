from __future__ import annotations

import math


def decay_weight(age_days: float, half_life_days: float) -> float:
    """Exponential decay weight with half-life in days."""
    if age_days < 0:
        return 0.0
    if half_life_days <= 0:
        return 0.0
    return math.pow(0.5, age_days / half_life_days)
