from __future__ import annotations

from datetime import datetime, timezone

import pytest

from repo_routing.boundary.models import (
    BoundaryDef,
    BoundaryModel,
    BoundaryUnit,
    Granularity,
    Membership,
    MembershipMode,
)


def _base_model(*, mode: MembershipMode, memberships: list[Membership]) -> BoundaryModel:
    return BoundaryModel(
        strategy_id="hybrid_path_cochange",
        strategy_version="v1",
        repo="octo-org/octo-repo",
        cutoff_utc=datetime(2026, 2, 11, 0, 0, tzinfo=timezone.utc),
        membership_mode=mode,
        units=[
            BoundaryUnit(unit_id="file:src/a.py", granularity=Granularity.FILE, path="src/a.py"),
            BoundaryUnit(unit_id="file:src/b.py", granularity=Granularity.FILE, path="src/b.py"),
        ],
        boundaries=[
            BoundaryDef(boundary_id="boundary:core", name="core", granularity=Granularity.DIR),
            BoundaryDef(boundary_id="boundary:ui", name="ui", granularity=Granularity.DIR),
        ],
        memberships=memberships,
    )


def test_hard_mode_requires_exactly_one_membership_per_unit() -> None:
    model = _base_model(
        mode=MembershipMode.HARD,
        memberships=[
            Membership(unit_id="file:src/a.py", boundary_id="boundary:core", weight=1.0),
            Membership(unit_id="file:src/b.py", boundary_id="boundary:ui", weight=1.0),
        ],
    )
    assert model.membership_mode == MembershipMode.HARD


@pytest.mark.parametrize(
    "mode,memberships,error_substr",
    [
        (
            MembershipMode.HARD,
            [
                Membership(unit_id="file:src/a.py", boundary_id="boundary:core", weight=1.0),
            ],
            "hard mode requires exactly 1 membership",
        ),
        (
            MembershipMode.OVERLAP,
            [
                Membership(unit_id="file:src/a.py", boundary_id="boundary:core", weight=1.0),
                Membership(unit_id="file:src/b.py", boundary_id="boundary:ui", weight=0.5),
            ],
            "overlap mode requires all weights to be 1.0",
        ),
        (
            MembershipMode.MIXED,
            [
                Membership(unit_id="file:src/a.py", boundary_id="boundary:core", weight=0.7),
                Membership(unit_id="file:src/a.py", boundary_id="boundary:ui", weight=0.2),
                Membership(unit_id="file:src/b.py", boundary_id="boundary:ui", weight=1.0),
            ],
            "mixed mode requires unit weights to sum to 1.0",
        ),
    ],
)
def test_membership_mode_invariants(
    mode: MembershipMode, memberships: list[Membership], error_substr: str
) -> None:
    with pytest.raises(ValueError, match=error_substr):
        _base_model(mode=mode, memberships=memberships)
