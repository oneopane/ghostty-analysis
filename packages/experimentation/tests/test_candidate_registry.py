from experimentation.workflow_registry import CandidateRegistry


def test_candidate_registry_promotes_champion(tmp_path) -> None:
    reg = CandidateRegistry(root=tmp_path)
    reg.register(task_id="reviewer_routing", candidate_ref="router.llm_rerank@v3")
    reg.promote(task_id="reviewer_routing", candidate_ref="router.llm_rerank@v3")

    state = reg.get(task_id="reviewer_routing")
    assert state["champion"] == "router.llm_rerank@v3"
