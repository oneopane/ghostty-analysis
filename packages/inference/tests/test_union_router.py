from __future__ import annotations

from datetime import datetime, timezone

from repo_routing.router.base import Evidence, RouteCandidate, RouteResult, Target, TargetType
from repo_routing.router.baselines.union import UnionRouter


class _FakeRouter:
    def __init__(self, candidates: list[RouteCandidate]) -> None:
        self._candidates = candidates

    def route(self, **kwargs):  # type: ignore[no-untyped-def]
        return RouteResult(
            repo=str(kwargs["repo"]),
            pr_number=int(kwargs["pr_number"]),
            as_of=kwargs["as_of"],
            top_k=int(kwargs.get("top_k", 5)),
            candidates=list(self._candidates),
            risk="low",
        )


def _candidate(name: str, score: float, kind: str) -> RouteCandidate:
    return RouteCandidate(
        target=Target(type=TargetType.user, name=name),
        score=score,
        evidence=[Evidence(kind=kind, data={})],
    )


def test_union_router_merges_candidates_and_preserves_sources() -> None:
    router = UnionRouter(
        source_routers=[
            ("mentions", _FakeRouter([_candidate("alice", 1.0, "mention")])),
            ("popularity", _FakeRouter([_candidate("alice", 0.5, "popularity"), _candidate("bob", 0.6, "popularity")])),
        ]
    )
    out = router.route(
        repo="acme/widgets",
        pr_number=7,
        as_of=datetime(2024, 1, 1, tzinfo=timezone.utc),
        top_k=5,
    )

    assert [c.target.name for c in out.candidates][:2] == ["alice", "bob"]
    ev = out.candidates[0].evidence
    assert any((e.data or {}).get("source_router") == "mentions" for e in ev)
    assert any((e.data or {}).get("source_router") == "popularity" for e in ev)
