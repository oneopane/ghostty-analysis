from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from ..models import BoundaryModel, MembershipMode


@dataclass(frozen=True)
class BoundaryInferenceContext:
    repo_full_name: str
    cutoff_utc: datetime
    data_dir: str | Path = "data"
    membership_mode: MembershipMode = MembershipMode.MIXED
    config: dict[str, Any] = field(default_factory=dict)


class BoundaryInferenceStrategy(Protocol):
    strategy_id: str
    strategy_version: str

    def infer(
        self,
        context: BoundaryInferenceContext,
    ) -> tuple[BoundaryModel, list[dict[str, Any]]]: ...
