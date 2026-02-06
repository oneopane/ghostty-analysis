from __future__ import annotations

from collections.abc import Iterable


def normalized_entropy(counts: Iterable[int]) -> float:
    """TODO: compute normalized Shannon entropy from non-negative counts.

    High level derivation:
    - Convert counts to probabilities p_i = c_i / sum(c).
    - Compute H = -sum(p_i * log(p_i)).
    - Optionally normalize by log(k) where k = number of non-zero buckets.

    Used by:
    - directory entropy feature
    - area entropy feature
    """
    raise NotImplementedError("TODO: implement entropy helper")


def median_int(values: list[int]) -> float:
    """TODO: compute median file churn.

    High level derivation:
    - Sort integer list.
    - Return middle value for odd n, avg of two middles for even n.
    """
    raise NotImplementedError("TODO: implement median helper")


def safe_ratio(numerator: float, denominator: float) -> float:
    """TODO: deterministic division helper returning 0.0 for denominator=0.

    Used by percentage/share features (status ratios, owner coverage, top-extension share).
    """
    raise NotImplementedError("TODO: implement ratio helper")
