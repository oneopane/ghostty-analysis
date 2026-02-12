from __future__ import annotations

from collections import defaultdict

from ..artifacts import BoundaryModelArtifact
from ..signals.path import normalize_path
from .models import BoundaryCoverageSummary, PRBoundaryFootprint


def project_files_to_boundary_footprint(
    *,
    paths: list[str],
    artifact: BoundaryModelArtifact,
) -> PRBoundaryFootprint:
    unit_to_boundary_weights: dict[str, dict[str, float]] = defaultdict(dict)
    for m in artifact.model.memberships:
        unit_to_boundary_weights[m.unit_id][m.boundary_id] = float(m.weight)

    file_boundaries: dict[str, list[str]] = {}
    file_boundary_weights: dict[str, dict[str, float]] = {}
    uncovered: list[str] = []

    for path in sorted({normalize_path(p) for p in paths}):
        unit_id = f"file:{path}"
        weights = unit_to_boundary_weights.get(unit_id)
        if not weights:
            uncovered.append(path)
            continue
        ordered = dict(sorted(weights.items(), key=lambda it: (-it[1], it[0])))
        file_boundary_weights[path] = ordered
        file_boundaries[path] = list(ordered.keys())

    boundaries = sorted(
        {b for bs in file_boundaries.values() for b in bs},
        key=str.lower,
    )

    return PRBoundaryFootprint(
        boundaries=boundaries,
        file_boundaries=file_boundaries,
        file_boundary_weights=file_boundary_weights,
        coverage=BoundaryCoverageSummary(
            changed_file_count=len(set(normalize_path(p) for p in paths)),
            covered_file_count=len(file_boundaries),
            uncovered_files=sorted(uncovered, key=str.lower),
        ),
        strategy_id=artifact.model.strategy_id,
        strategy_version=artifact.model.strategy_version,
    )
