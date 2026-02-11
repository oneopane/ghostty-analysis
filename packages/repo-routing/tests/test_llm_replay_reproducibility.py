from __future__ import annotations

from datetime import datetime, timezone

from repo_routing.router.base import Evidence, RouteCandidate, RouteResult, Target, TargetType
from repo_routing.router.llm_cache import LLMReplayCache
from repo_routing.router.llm_rerank import LLMRerankRouter


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
                    score=0.8,
                    evidence=[Evidence(kind="popularity", data={"source_router": "popularity"})],
                ),
            ],
            risk="low",
        )


def test_llm_replay_mode_is_deterministic_from_cache(tmp_path) -> None:  # type: ignore[no-untyped-def]
    cache = LLMReplayCache(cache_dir=tmp_path / "cache")
    live = LLMRerankRouter(
        mode="live",
        union_router=_FakeUnion(),  # type: ignore[arg-type]
        cache=cache,
    )
    replay = LLMRerankRouter(
        mode="replay",
        union_router=_FakeUnion(),  # type: ignore[arg-type]
        cache=cache,
    )
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    live_out = live.route(repo="acme/widgets", pr_number=3, as_of=ts, top_k=5)
    replay_out = replay.route(repo="acme/widgets", pr_number=3, as_of=ts, top_k=5)

    left = [c.model_dump(mode="json") for c in live_out.candidates]
    right = [c.model_dump(mode="json") for c in replay_out.candidates]
    assert left == right
