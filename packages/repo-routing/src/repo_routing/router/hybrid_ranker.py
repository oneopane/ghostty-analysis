from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import TYPE_CHECKING

from .base import Evidence, RouteCandidate, RouteResult
from .baselines.union import UnionRouter

if TYPE_CHECKING:
    from ..inputs.models import PRInputBundle


class HybridRankerRouter:
    """Deterministic weighted reranker over union candidates."""

    def __init__(
        self,
        *,
        weights: dict[str, float] | None = None,
        union_router: UnionRouter | None = None,
    ) -> None:
        self.union_router = union_router or UnionRouter()
        self.weights = weights or {
            "mentions": 1.0,
            "popularity": 0.8,
            "codeowners": 1.2,
            "stewards": 1.1,
        }
        payload = json.dumps(
            self.weights,
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
        )
        self.weights_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self.provenance: dict[str, object] = {
            "ranker_version": "hybrid_ranker_v1",
            "weights": dict(self.weights),
            "weights_hash": self.weights_hash,
        }

    def _candidate_score(self, candidate: RouteCandidate) -> tuple[float, list[str]]:
        source_scores: dict[str, float] = {}
        for ev in candidate.evidence:
            source = str((ev.data or {}).get("source_router") or "").strip().lower()
            if not source:
                continue
            source_scores[source] = max(
                source_scores.get(source, 0.0),
                float(self.weights.get(source, 0.0)),
            )
        weighted = sum(source_scores.values())
        score = weighted * 10.0 + float(candidate.score)
        return score, sorted(source_scores.keys())

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
        union_result = self.union_router.route(
            repo=repo,
            pr_number=pr_number,
            as_of=as_of,
            data_dir=data_dir,
            top_k=max(top_k, 10),
            input_bundle=input_bundle,
        )

        rescored: list[RouteCandidate] = []
        for cand in union_result.candidates:
            score, sources = self._candidate_score(cand)
            rescored.append(
                RouteCandidate(
                    target=cand.target,
                    score=score,
                    evidence=[
                        *cand.evidence,
                        Evidence(
                            kind="hybrid_ranker",
                            data={
                                "ranker_version": "hybrid_ranker_v1",
                                "weights_hash": self.weights_hash,
                                "sources": sources,
                            },
                        ),
                    ],
                )
            )

        rescored.sort(key=lambda c: (-c.score, c.target.name.lower()))
        return RouteResult(
            repo=repo,
            pr_number=pr_number,
            as_of=as_of,
            top_k=top_k,
            candidates=rescored[:top_k],
            risk=union_result.risk,
            confidence="medium" if rescored else "low",
            notes=[*union_result.notes, "ranker=hybrid_ranker_v1", f"weights_hash={self.weights_hash}"],
        )
