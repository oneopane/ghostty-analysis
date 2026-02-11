from __future__ import annotations

from datetime import datetime, timezone

from repo_routing.router.base import Evidence, RouteCandidate, RouteResult, Target, TargetType
from repo_routing.router.hybrid_ranker import HybridRankerRouter


class _FakeUnion:
    def route(self, **kwargs):  # type: ignore[no-untyped-def]
        return RouteResult(
            repo=str(kwargs["repo"]),
            pr_number=int(kwargs["pr_number"]),
            as_of=kwargs["as_of"],
            top_k=int(kwargs.get("top_k", 5)),
            candidates=[
                RouteCandidate(
                    target=Target(type=TargetType.user, name="alice"),
                    score=1.0,
                    evidence=[Evidence(kind="mention", data={"source_router": "mentions"})],
                ),
                RouteCandidate(
                    target=Target(type=TargetType.user, name="bob"),
                    score=1.0,
                    evidence=[
                        Evidence(kind="popularity", data={"source_router": "popularity"}),
                        Evidence(kind="codeowners", data={"source_router": "codeowners"}),
                    ],
                ),
            ],
            risk="low",
        )


def test_hybrid_ranker_prefers_weighted_multi_source_candidate() -> None:
    router = HybridRankerRouter(union_router=_FakeUnion())  # type: ignore[arg-type]
    out = router.route(
        repo="acme/widgets",
        pr_number=9,
        as_of=datetime(2024, 1, 1, tzinfo=timezone.utc),
        top_k=5,
    )
    assert out.candidates
    assert out.candidates[0].target.name == "bob"
    assert any(n.startswith("weights_hash=") for n in out.notes)
