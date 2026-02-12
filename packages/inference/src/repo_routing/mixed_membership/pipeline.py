from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .areas.basis import build_user_area_activity_rows, pr_area_distribution_from_paths
from .artifacts import AreaMembershipModelArtifact
from .config import AreaMembershipConfig
from .models.nmf import (
    build_candidate_role_mix_features,
    build_pair_role_affinity_features,
    fit_area_membership_nmf,
)


def fit_area_membership_model(
    *,
    repo: str,
    cutoff: datetime,
    data_dir: str | Path = "data",
    config: AreaMembershipConfig | None = None,
) -> AreaMembershipModelArtifact:
    """End-to-end function API for marimo exploration (no script required)."""
    cfg = config or AreaMembershipConfig()
    rows = build_user_area_activity_rows(
        repo=repo,
        cutoff=cutoff,
        data_dir=data_dir,
        config=cfg,
    )
    return fit_area_membership_nmf(
        repo=repo,
        cutoff=cutoff,
        rows=rows,
        config=cfg,
    )


def derive_role_features_for_pr(
    *,
    model: AreaMembershipModelArtifact,
    repo: str,
    pr_paths: list[str],
    candidate_logins: list[str],
    data_dir: str | Path = "data",
) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, float]]]:
    """Derive candidate + pair role features for one PR context."""
    pr_dist = pr_area_distribution_from_paths(repo=repo, paths=pr_paths, data_dir=data_dir)
    cand = build_candidate_role_mix_features(model=model, candidate_logins=candidate_logins)
    pair = build_pair_role_affinity_features(
        model=model,
        pr_area_distribution=pr_dist,
        candidate_logins=candidate_logins,
    )
    return cand, pair
