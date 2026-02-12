from __future__ import annotations

from collections.abc import Mapping


def linear_score(features: Mapping[str, float], weights: Mapping[str, float]) -> float:
    total = 0.0
    for key, weight in weights.items():
        total += float(weight) * float(features.get(key, 0.0))
    return total
