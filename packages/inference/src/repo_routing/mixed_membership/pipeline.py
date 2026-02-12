from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .artifacts import BoundaryMembershipModelArtifact
from .boundaries.basis import (
    build_user_boundary_activity_rows,
    pr_boundary_distribution_from_paths,
)
from .config import BoundaryMembershipConfig
from .models.nmf import (
    build_candidate_role_mix_features,
    build_pair_role_affinity_features,
    fit_boundary_membership_nmf,
)


def fit_boundary_membership_model(
    *,
    repo: str,
    cutoff: datetime,
    data_dir: str | Path = "data",
    config: BoundaryMembershipConfig | None = None,
) -> BoundaryMembershipModelArtifact:
    cfg = config or BoundaryMembershipConfig()
    rows = build_user_boundary_activity_rows(
        repo=repo,
        cutoff=cutoff,
        data_dir=data_dir,
        config=cfg,
    )
    return fit_boundary_membership_nmf(
        repo=repo,
        cutoff=cutoff,
        rows=rows,
        config=cfg,
    )


def derive_role_features_for_pr(
    *,
    model: BoundaryMembershipModelArtifact,
    repo: str,
    pr_paths: list[str],
    candidate_logins: list[str],
    data_dir: str | Path = "data",
) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, float]]]:
    pr_dist = pr_boundary_distribution_from_paths(repo=repo, paths=pr_paths, data_dir=data_dir)
    cand = build_candidate_role_mix_features(model=model, candidate_logins=candidate_logins)
    pair = build_pair_role_affinity_features(
        model=model,
        pr_boundary_distribution=pr_dist,
        candidate_logins=candidate_logins,
    )
    return cand, pair
