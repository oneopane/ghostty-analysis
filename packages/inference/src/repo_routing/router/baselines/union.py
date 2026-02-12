from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from ..base import Evidence, RouteCandidate, RouteResult, TargetType
from .codeowners import CodeownersRouter
from .mentions import MentionsRouter
from .popularity import PopularityRouter

if TYPE_CHECKING:
    from ...inputs.models import PRInputBundle


class UnionRouter:
    """Deterministic candidate union over baseline routers."""

    def __init__(
        self,
        *,
        include_mentions: bool = True,
        include_popularity: bool = True,
        include_codeowners: bool = True,
        source_routers: list[tuple[str, object]] | None = None,
    ) -> None:
        if source_routers is not None:
            self._routers = list(source_routers)
            return

        self._routers: list[tuple[str, object]] = []
        if include_mentions:
            self._routers.append(("mentions", MentionsRouter()))
        if include_popularity:
            self._routers.append(("popularity", PopularityRouter(lookback_days=180)))
        if include_codeowners:
            self._routers.append(("codeowners", CodeownersRouter(enabled=True)))

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
        merged: dict[tuple[TargetType, str], dict[str, object]] = {}
        notes: list[str] = []

        for source_name, router in self._routers:
            result = router.route(  # type: ignore[attr-defined]
                repo=repo,
                pr_number=pr_number,
                as_of=as_of,
                data_dir=data_dir,
                top_k=max(top_k, 10),
                input_bundle=input_bundle,
            )
            notes.append(f"source={source_name}:{len(result.candidates)}")
            for cand in result.candidates:
                key = (cand.target.type, cand.target.name.lower())
                bucket = merged.setdefault(
                    key,
                    {
                        "target": cand.target,
                        "max_score": 0.0,
                        "score_sum": 0.0,
                        "sources": set(),
                        "evidence": [],
                    },
                )
                bucket["max_score"] = max(float(bucket["max_score"]), float(cand.score))
                bucket["score_sum"] = float(bucket["score_sum"]) + float(cand.score)
                sources = bucket["sources"]
                if isinstance(sources, set):
                    sources.add(source_name)
                evidence = bucket["evidence"]
                if isinstance(evidence, list):
                    for ev in cand.evidence:
                        evidence.append(
                            Evidence(
                                kind=ev.kind,
                                data={
                                    "source_router": source_name,
                                    **dict(ev.data or {}),
                                },
                            )
                        )

        candidates: list[RouteCandidate] = []
        for _, bucket in merged.items():
            sources = bucket["sources"]
            source_count = len(sources) if isinstance(sources, set) else 0
            score = (
                float(source_count) * 10.0
                + float(bucket["max_score"])
                + float(bucket["score_sum"]) * 0.01
            )
            candidates.append(
                RouteCandidate(
                    target=bucket["target"],  # type: ignore[arg-type]
                    score=score,
                    evidence=bucket["evidence"],  # type: ignore[arg-type]
                )
            )

        candidates.sort(key=lambda c: (-c.score, c.target.name.lower()))
        return RouteResult(
            repo=repo,
            pr_number=pr_number,
            as_of=as_of,
            top_k=top_k,
            candidates=candidates[:top_k],
            risk="low" if candidates else "high",
            notes=notes,
        )
