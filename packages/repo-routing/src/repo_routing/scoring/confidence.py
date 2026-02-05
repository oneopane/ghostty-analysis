from __future__ import annotations

from .config import ThresholdsConfig


def confidence_from_scores(scores: list[float], thresholds: ThresholdsConfig) -> str:
    if not scores:
        return "low"
    ordered = sorted(scores, reverse=True)
    s1 = ordered[0]
    s2 = ordered[1] if len(ordered) > 1 else 0.0
    margin = s1 - s2
    if margin >= thresholds.confidence_high_margin:
        return "high"
    if margin >= thresholds.confidence_med_margin:
        return "medium"
    return "low"
