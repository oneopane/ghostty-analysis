from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

FeatureScalar = int | float | bool | str | None
PRFeatureVector = dict[str, FeatureScalar]
CandidateFeatureVector = dict[str, FeatureScalar]
CandidateFeatureTable = dict[str, CandidateFeatureVector]


@dataclass(frozen=True)
class FeatureExtractionConfig:
    """Configuration scaffold for feature extraction.

    This is intentionally small and stable so routers can hash config cleanly.
    """

    feature_version: str = "v1"
    data_dir: str | Path = "data"

    # Candidate activity windows for features 50+.
    candidate_windows_days: tuple[int, ...] = (30, 90, 180)

    # Whether to include expensive SQL-backed families.
    include_pr_timeline_features: bool = True
    include_ownership_features: bool = True
    include_candidate_features: bool = True


@dataclass(frozen=True)
class FeatureExtractionContext:
    """Derived context passed into family builders.

    This keeps function signatures typed and avoids repeated parameter threading.
    """

    repo: str
    pr_number: int
    cutoff: datetime
    data_dir: str | Path
