from __future__ import annotations

import math
from collections.abc import Iterable


def normalized_entropy(counts: Iterable[int]) -> float:
    """Compute normalized Shannon entropy from non-negative counts.

    Returns 0.0 for empty or degenerate inputs (all mass in one bucket).
    """

    xs = [int(c) for c in counts if int(c) > 0]
    total = sum(xs)
    if total <= 0:
        return 0.0

    k = len(xs)
    if k <= 1:
        return 0.0

    probs = [x / total for x in xs]
    h = -sum(p * math.log(p) for p in probs if p > 0.0)
    return h / math.log(k)


def median_int(values: list[int]) -> float:
    """Compute median over integer values.

    Returns 0.0 for empty input.
    """

    if not values:
        return 0.0

    xs = sorted(int(v) for v in values)
    n = len(xs)
    mid = n // 2
    if n % 2 == 1:
        return float(xs[mid])
    return float(xs[mid - 1] + xs[mid]) / 2.0


def safe_ratio(numerator: float, denominator: float) -> float:
    """Deterministic division helper returning 0.0 for denominator <= 0."""

    if denominator <= 0.0:
        return 0.0
    return float(numerator) / float(denominator)
