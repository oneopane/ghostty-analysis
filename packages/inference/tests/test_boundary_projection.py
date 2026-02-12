from __future__ import annotations

from datetime import datetime, timezone

from repo_routing.boundary.artifacts import BoundaryManifest, BoundaryModelArtifact
from repo_routing.boundary.consumption import project_files_to_boundary_footprint
from repo_routing.boundary.models import (
    BoundaryDef,
    BoundaryModel,
    BoundaryUnit,
    Granularity,
    Membership,
    MembershipMode,
)


def _artifact() -> BoundaryModelArtifact:
    model = BoundaryModel(
        strategy_id="hybrid_path_cochange.v1",
        strategy_version="v1",
        repo="acme/widgets",
        cutoff_utc=datetime(2024, 1, 10, tzinfo=timezone.utc),
        membership_mode=MembershipMode.MIXED,
        units=[
            BoundaryUnit(unit_id="file:src/a.py", granularity=Granularity.FILE, path="src/a.py"),
            BoundaryUnit(unit_id="file:tests/test_a.py", granularity=Granularity.FILE, path="tests/test_a.py"),
        ],
        boundaries=[
            BoundaryDef(boundary_id="dir:src", name="src", granularity=Granularity.DIR),
            BoundaryDef(boundary_id="dir:tests", name="tests", granularity=Granularity.DIR),
        ],
        memberships=[
            Membership(unit_id="file:src/a.py", boundary_id="dir:src", weight=0.8),
            Membership(unit_id="file:src/a.py", boundary_id="dir:tests", weight=0.2),
            Membership(unit_id="file:tests/test_a.py", boundary_id="dir:tests", weight=1.0),
        ],
    )
    manifest = BoundaryManifest(
        schema_version=model.schema_version,
        strategy_id=model.strategy_id,
        strategy_version=model.strategy_version,
        repo=model.repo,
        cutoff_utc=model.cutoff_utc,
        model_hash="x",
        unit_count=2,
        boundary_count=2,
        membership_count=3,
    )
    return BoundaryModelArtifact(model=model, manifest=manifest)


def test_projection_is_deterministic_and_reports_coverage() -> None:
    artifact = _artifact()
    footprint = project_files_to_boundary_footprint(
        paths=["tests/test_a.py", "src/a.py", "missing.txt", "src/a.py"],
        artifact=artifact,
    )

    assert footprint.boundaries == ["dir:src", "dir:tests"]
    assert footprint.file_boundaries["src/a.py"] == ["dir:src", "dir:tests"]
    assert footprint.file_boundary_weights["src/a.py"]["dir:src"] == 0.8
    assert footprint.coverage.changed_file_count == 3
    assert footprint.coverage.covered_file_count == 2
    assert footprint.coverage.uncovered_files == ["missing.txt"]
