from __future__ import annotations

from pydantic import BaseModel


class RepoRoutingConfig(BaseModel):
    repo: str
    data_dir: str = "data"
