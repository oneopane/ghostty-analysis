from repo_routing.operators.registry import list_operator_ids


def test_builtin_router_operators_are_registered() -> None:
    ids = list_operator_ids(task_id="reviewer_routing")
    assert "router.mentions" in ids
    assert "router.llm_rerank" in ids
