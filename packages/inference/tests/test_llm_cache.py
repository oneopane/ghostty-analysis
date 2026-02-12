from __future__ import annotations

from repo_routing.router.llm_cache import LLMReplayCache


def test_llm_replay_cache_roundtrip(tmp_path) -> None:  # type: ignore[no-untyped-def]
    cache = LLMReplayCache(cache_dir=tmp_path / "cache")
    assert cache.get("k1") is None
    cache.put("k1", {"model": "dummy", "items": []})
    got = cache.get("k1")
    assert isinstance(got, dict)
    assert got.get("model") == "dummy"
