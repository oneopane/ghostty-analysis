from repo_routing.router.llm_cache import LLMSemanticCache, LLMSemanticCacheKey


def test_llm_semantic_cache_roundtrip(tmp_path) -> None:
    cache = LLMSemanticCache(root=tmp_path)
    key = LLMSemanticCacheKey(
        repo="acme/widgets",
        entity_type="pull_request",
        entity_id="7",
        cutoff="2026-02-01T00:00:00Z",
        artifact_type="llm_rerank_response",
        version_key="model=dummy|prompt=abc|temp=0",
    )

    assert cache.get(key) is None
    cache.put(key=key, value={"items": []})
    assert cache.get(key) == {"items": []}
