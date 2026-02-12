from __future__ import annotations

from pydantic import BaseModel, Field


class BoundaryCoverageSummary(BaseModel):
    changed_file_count: int = 0
    covered_file_count: int = 0
    uncovered_files: list[str] = Field(default_factory=list)

    @property
    def coverage_ratio(self) -> float:
        if self.changed_file_count <= 0:
            return 0.0
        return float(self.covered_file_count) / float(self.changed_file_count)


class PRBoundaryFootprint(BaseModel):
    boundaries: list[str] = Field(default_factory=list)
    file_boundaries: dict[str, list[str]] = Field(default_factory=dict)
    file_boundary_weights: dict[str, dict[str, float]] = Field(default_factory=dict)
    coverage: BoundaryCoverageSummary = Field(default_factory=BoundaryCoverageSummary)
    strategy_id: str | None = None
    strategy_version: str | None = None
