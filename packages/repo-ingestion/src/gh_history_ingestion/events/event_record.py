from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EventRecord:
    repo_id: int
    occurred_at: Any
    actor_id: int | None
    subject_type: str
    subject_id: int
    event_type: str
    object_type: str | None = None
    object_id: int | None = None
    commit_sha: str | None = None
    payload: dict | None = None
