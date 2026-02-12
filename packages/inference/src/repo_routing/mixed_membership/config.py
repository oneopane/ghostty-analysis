from __future__ import annotations

from pydantic import BaseModel, Field


class BoundaryMembershipConfig(BaseModel):
    """Configuration for boundary-basis mixed-membership exploration."""

    version: str = "mm.boundary.nmf.v1"
    basis_version: str = "hybrid_path_cochange.v1"

    lookback_days: int = Field(default=180, ge=1)

    include_authored: bool = True
    include_reviews: bool = True
    include_comments: bool = True

    weight_authored: float = Field(default=0.5, ge=0.0)
    weight_review: float = Field(default=1.0, ge=0.0)
    weight_comment: float = Field(default=0.3, ge=0.0)

    exclude_bots: bool = True

    n_components: int = Field(default=6, ge=1)
    random_state: int = 17
    max_iter: int = Field(default=400, ge=50)
    init: str = "nndsvda"

    min_user_total_weight: float = Field(default=0.0, ge=0.0)

    top_role_boundaries: int = Field(default=8, ge=1)
