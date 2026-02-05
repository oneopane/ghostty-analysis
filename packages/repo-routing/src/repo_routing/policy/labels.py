from __future__ import annotations

from ..analysis.models import AnalysisResult
from ..scoring.config import ScoringConfig


def suggest_labels(
    result: AnalysisResult, *, config: ScoringConfig | None = None
) -> list[str]:
    labels: list[str] = []

    if result.gates.missing_issue:
        labels.append("needs-issue-link")
    if result.gates.missing_ai_disclosure:
        labels.append("needs-ai-disclosure")
    if result.gates.missing_provenance:
        labels.append("needs-provenance")

    if result.risk == "high":
        labels.append("routed-high-risk")

    if result.candidates:
        labels.append("suggested-steward-review")

    include_area_labels = (
        config.labels.include_area_labels if config is not None else False
    )
    if include_area_labels:
        for area in sorted(set(result.areas), key=lambda s: s.lower()):
            labels.append(f"routed-area:{area}")

    return labels
