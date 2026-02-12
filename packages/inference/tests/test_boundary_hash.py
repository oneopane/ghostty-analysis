from __future__ import annotations

from datetime import datetime, timezone

from repo_routing.boundary.hash import boundary_model_hash
from repo_routing.boundary.models import (
    BoundaryDef,
    BoundaryModel,
    BoundaryUnit,
    Granularity,
    Membership,
    MembershipMode,
)


def _model_with_order(order: int) -> BoundaryModel:
    units = [
        BoundaryUnit(unit_id="file:src/a.py", granularity=Granularity.FILE, path="src/a.py"),
        BoundaryUnit(unit_id="file:src/b.py", granularity=Granularity.FILE, path="src/b.py"),
    ]
    boundaries = [
        BoundaryDef(boundary_id="boundary:core", name="core", granularity=Granularity.DIR),
        BoundaryDef(boundary_id="boundary:ui", name="ui", granularity=Granularity.DIR),
    ]
    memberships = [
        Membership(unit_id="file:src/a.py", boundary_id="boundary:core", weight=1.0),
        Membership(unit_id="file:src/b.py", boundary_id="boundary:ui", weight=1.0),
    ]
    if order == 2:
        units = list(reversed(units))
        boundaries = list(reversed(boundaries))
        memberships = list(reversed(memberships))

    return BoundaryModel(
        strategy_id="hybrid_path_cochange",
        strategy_version="v1",
        repo="octo-org/octo-repo",
        cutoff_utc=datetime(2026, 2, 11, 0, 0, tzinfo=timezone.utc),
        membership_mode=MembershipMode.HARD,
        units=units,
        boundaries=boundaries,
        memberships=memberships,
        metadata={"alpha": 1, "zeta": 2},
    )


def test_boundary_hash_is_stable_across_input_orderings() -> None:
    model_a = _model_with_order(1)
    model_b = _model_with_order(2)

    assert boundary_model_hash(model_a) == boundary_model_hash(model_b)
