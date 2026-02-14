from sdlc_core.store.prompt_store import PromptStore
from sdlc_core.types.prompt import PromptSpec


def test_prompt_store_register_and_get(tmp_path) -> None:
    store = PromptStore(root=tmp_path)
    spec = PromptSpec(
        prompt_id="reviewer_rerank",
        prompt_version="v1",
        template="Rank candidates for PR {{ pr_number }}",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )
    ref = store.register(spec)
    loaded = store.get(prompt_id="reviewer_rerank", prompt_version="v1")

    assert ref.prompt_id == "reviewer_rerank"
    assert loaded is not None
    assert loaded.template.startswith("Rank candidates")
