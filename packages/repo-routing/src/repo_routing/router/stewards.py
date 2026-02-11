from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ..analysis.engine import analyze_pr

if TYPE_CHECKING:
    from ..inputs.models import PRInputBundle
from ..router.base import RouteCandidate, RouteResult, Target, TargetType


class StewardsRouter:
    def __init__(self, *, config_path: str | Path) -> None:
        self.config_path = Path(config_path)

    def route(
        self,
        *,
        repo: str,
        pr_number: int,
        as_of: datetime,
        data_dir: str = "data",
        top_k: int = 5,
        input_bundle: PRInputBundle | None = None,
    ) -> RouteResult:
        analysis = analyze_pr(
            repo=repo,
            pr_number=pr_number,
            cutoff=as_of,
            data_dir=data_dir,
            config_path=self.config_path,
        )

        candidates = [
            RouteCandidate(
                target=Target(type=TargetType.user, name=c.login),
                score=c.score,
                evidence=c.evidence,
            )
            for c in analysis.candidates[:top_k]
        ]

        return RouteResult(
            repo=repo,
            pr_number=pr_number,
            as_of=as_of,
            top_k=top_k,
            candidates=candidates,
            risk=analysis.risk,
            confidence=analysis.confidence,
            notes=analysis.notes,
        )
