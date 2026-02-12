from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class IngestCheckpoint:
    flow: str
    stage: str
    completed_at: datetime
    details: dict[str, Any] = field(default_factory=dict)


class IngestStagePipeline:
    """Lightweight stage/checkpoint recorder for ingest orchestration flows."""

    def __init__(self, *, flow: str) -> None:
        self.flow = flow
        self._checkpoints: list[IngestCheckpoint] = []

    @property
    def checkpoints(self) -> tuple[IngestCheckpoint, ...]:
        return tuple(self._checkpoints)

    def checkpoint(self, stage: str, **details: Any) -> None:
        self._checkpoints.append(
            IngestCheckpoint(
                flow=self.flow,
                stage=stage,
                completed_at=datetime.now(timezone.utc),
                details={k: v for k, v in details.items()},
            )
        )
