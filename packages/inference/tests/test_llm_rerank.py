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
                    score=0.5,
                    evidence=[Evidence(kind="popularity", data={"source_router": "popularity"})],
                ),
            ],
            risk="low",
        )


def test_llm_rerank_off_mode_returns_union(tmp_path) -> None:  # type: ignore[no-untyped-def]
    router = LLMRerankRouter(
        mode="off",
        union_router=_FakeUnion(),  # type: ignore[arg-type]
        cache=LLMReplayCache(cache_dir=tmp_path / "cache"),
    )
    out = router.route(
        repo="acme/widgets",
        pr_number=1,
        as_of=datetime(2024, 1, 1, tzinfo=timezone.utc),
        top_k=5,
    )
    assert out.candidates[0].target.name == "alice"
    assert "llm_mode=off" in out.notes


def test_llm_rerank_live_mode_emits_steps_and_provenance(tmp_path) -> None:  # type: ignore[no-untyped-def]
    cache = LLMReplayCache(cache_dir=tmp_path / "cache")
    router = LLMRerankRouter(
        mode="live",
        union_router=_FakeUnion(),  # type: ignore[arg-type]
        cache=cache,
    )
    out = router.route(
        repo="acme/widgets",
        pr_number=2,
        as_of=datetime(2024, 1, 1, tzinfo=timezone.utc),
        top_k=5,
    )
    assert out.candidates
    assert router.last_llm_steps.get("request") is not None
    assert router.last_llm_steps.get("response") is not None
    assert router.last_provenance.get("cache_status") == "live_write"
