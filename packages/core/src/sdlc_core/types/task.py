from __future__ import annotations

from pydantic import BaseModel


class TaskSpec(BaseModel):
    task_id: str
    objective: str
    truth_primary_policy: str | None = None
