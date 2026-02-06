from __future__ import annotations

from pathlib import Path
from typing import Any

from ..inputs.models import PRInputBundle
from .base import FeatureExtractor
from .features.candidate_activity import build_candidate_activity_table
from .features.interaction import build_interaction_features
from .features.ownership import build_ownership_features
from .features.pr_surface import build_pr_surface_features
from .features.pr_timeline import build_pr_timeline_features
from .features.schemas import FeatureExtractionConfig


class AttentionRoutingFeatureExtractorV1(FeatureExtractor):
    """Stub extractor orchestrating the feature families in deterministic order.

    Intended output schema:
    {
      "feature_version": "v1",
      "repo": ...,
      "pr_number": ...,
      "cutoff": ...,
      "pr": {...},
      "candidates": {login: {...}},
      "interactions": {login: {...}},
      "meta": {...}
    }
    """

    def __init__(self, *, config: FeatureExtractionConfig | None = None) -> None:
        self.config = config or FeatureExtractionConfig()

    def extract(self, input: PRInputBundle) -> dict[str, Any]:
        """TODO: compose all families.

        High-level implementation plan:
        1) Build PR surface features (#1-#25) from bundle fields.
        2) Optionally build timeline/as-of features (#26-#40) via cutoff-bounded SQL.
        3) Optionally build ownership features (#41-#48) from pinned CODEOWNERS + areas.
        4) Build candidate pool deterministically, then candidate activity features (#49-#50).
        5) Build optional interaction features.
        6) Return stable JSON-serializable structure with sorted keys/order.
        """
        raise NotImplementedError

    def _candidate_pool(self, input: PRInputBundle) -> list[str]:
        """TODO: define deterministic candidate pool builder.

        High-level options:
        - active participants in recent repo window from history DB
        - current review requests
        - mentioned users
        - codeowners matched users

        Must be cutoff-safe and bot/author filtering should be explicit.
        """
        raise NotImplementedError


def build_feature_extractor_v1(
    *,
    data_dir: str | Path = "data",
    include_pr_timeline_features: bool = True,
    include_ownership_features: bool = True,
    include_candidate_features: bool = True,
) -> AttentionRoutingFeatureExtractorV1:
    """Factory helper for router construction and import-path loaders."""
    cfg = FeatureExtractionConfig(
        data_dir=data_dir,
        include_pr_timeline_features=include_pr_timeline_features,
        include_ownership_features=include_ownership_features,
        include_candidate_features=include_candidate_features,
    )
    return AttentionRoutingFeatureExtractorV1(config=cfg)
