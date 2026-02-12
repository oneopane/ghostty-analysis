from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from gh.storage.upsert import (
    list_ingestion_checkpoint_stages,
    upsert_ingestion_checkpoint,
)


@dataclass(frozen=True)
class IngestCheckpoint:
    flow: str
    stage: str
    completed_at: datetime
    details: dict[str, Any] = field(default_factory=dict)


class IngestStagePipeline:
    """Lightweight stage/checkpoint recorder for ingest orchestration flows."""

    def __init__(
        self,
        *,
        flow: str,
        session=None,
        repo_id: int | None = None,
        resume: bool = False,
    ) -> None:
        self.flow = flow
        self._session = session
        self._repo_id = repo_id
        self._resume = bool(resume and session is not None and repo_id is not None)
        self._completed_stages: set[str] = set()
        if self._resume:
            self._completed_stages = list_ingestion_checkpoint_stages(
                session,
                repo_id=repo_id,  # type: ignore[arg-type]
                flow=flow,
            )
        self._checkpoints: list[IngestCheckpoint] = []

    @property
    def checkpoints(self) -> tuple[IngestCheckpoint, ...]:
        return tuple(self._checkpoints)

    def should_skip(self, stage: str) -> bool:
        return stage in self._completed_stages

    def checkpoint(self, stage: str, **details: Any) -> None:
        record = IngestCheckpoint(
            flow=self.flow,
            stage=stage,
            completed_at=datetime.now(timezone.utc),
            details={k: v for k, v in details.items()},
        )
        self._checkpoints.append(record)
        self._completed_stages.add(stage)
        if self._session is not None and self._repo_id is not None:
            upsert_ingestion_checkpoint(
                self._session,
                repo_id=self._repo_id,
                flow=self.flow,
                stage=stage,
                details_json=json.dumps(record.details, sort_keys=True, ensure_ascii=True),
                completed_at=record.completed_at,
            )
            self._session.commit()

    @property
    def resumed_stages(self) -> tuple[str, ...]:
        return tuple(sorted(self._completed_stages, key=str.lower))
