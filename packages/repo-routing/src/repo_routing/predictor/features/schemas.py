from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

FeatureScalar = int | float | bool | str | None
PRFeatureVector = dict[str, Any]
CandidateFeatureVector = dict[str, Any]
CandidateFeatureTable = dict[str, CandidateFeatureVector]


@dataclass(frozen=True)
class FeatureExtractionConfig:
    """Configuration scaffold for feature extraction.

    This is intentionally small and stable so routers can hash config cleanly.
    """

    feature_version: str = "v1"
    data_dir: str | Path = "data"

    # Candidate activity windows for features.
    candidate_windows_days: tuple[int, ...] = (7, 30, 90, 180)

    # Whether to include expensive SQL-backed families.
    include_pr_timeline_features: bool = True
    include_ownership_features: bool = True
    include_candidate_features: bool = True

    # Deterministic feature family versions.
    candidate_gen_version: str = "cg.v1"
    ownership_version: str = "ownership.v1"
    trajectory_version: str = "trajectory.v1"
    affinity_version: str = "affinity.v1"
    priors_version: str = "priors.v1"
    similarity_version: str = "sim.v1"
    automation_version: str = "automation.v1"

    # Optional task policy hook (e.g. T02/T04/T06)
    task_id: str | None = None


@dataclass(frozen=True)
class FeatureExtractionContext:
    """Derived context passed into family builders.

    This keeps function signatures typed and avoids repeated parameter threading.
    """

    repo: str
    pr_number: int
    cutoff: datetime
    data_dir: str | Path
