from __future__ import annotations

from datetime import datetime

from ...history.index import popularity_index
from ...history.reader import HistoryReader
from ..base import Evidence, RouteCandidate, RouteResult, Target, TargetType


class PopularityRouter:
    """Baseline: route to recent reviewers/commenters (offline)."""

    def __init__(self, *, lookback_days: int = 180) -> None:
        self.lookback_days = lookback_days

    def route(
        self,
        *,
        repo: str,
        pr_number: int,
        as_of: datetime,
        data_dir: str = "data",
        top_k: int = 5,
    ) -> RouteResult:
        with HistoryReader(repo_full_name=repo, data_dir=data_dir) as reader:
            pr = reader.pull_request_snapshot(number=pr_number, as_of=as_of)
            ranked = popularity_index(
                reader, as_of=as_of, lookback_days=self.lookback_days
            )

        author = (pr.author_login or "").lower()
        ranked = [r for r in ranked if r.login.lower() != author]
        if not ranked:
            return RouteResult(
                repo=repo,
                pr_number=pr_number,
                as_of=as_of,
                top_k=top_k,
                candidates=[],
                risk="high",
                notes=["no candidates in lookback window"],
            )

        max_count = max(r.count for r in ranked)
        candidates: list[RouteCandidate] = []
        for r in ranked[:top_k]:
            score = 0.0 if max_count <= 0 else (r.count / max_count)
            candidates.append(
                RouteCandidate(
                    target=Target(type=TargetType.user, name=r.login),
                    score=score,
                    evidence=[
                        Evidence(
                            kind="popularity",
                            data={
                                "count": r.count,
                                "lookback_days": self.lookback_days,
                            },
                        )
                    ],
                )
            )

        return RouteResult(
            repo=repo,
            pr_number=pr_number,
            as_of=as_of,
            top_k=top_k,
            candidates=candidates,
            risk="low",
        )
