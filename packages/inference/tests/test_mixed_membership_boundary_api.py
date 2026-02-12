from __future__ import annotations

from repo_routing.mixed_membership import (
    BoundaryMembershipConfig,
    BoundaryMembershipModelArtifact,
    build_boundary_membership_dataset,
    build_boundary_membership_matrix,
    derive_role_features_for_pr,
    fit_boundary_membership_model,
)


def test_boundary_api_exports() -> None:
    assert BoundaryMembershipConfig is not None
    assert BoundaryMembershipModelArtifact is not None
    assert build_boundary_membership_dataset is not None
    assert build_boundary_membership_matrix is not None
    assert derive_role_features_for_pr is not None
    assert fit_boundary_membership_model is not None
