from repo_routing.semantic.backfill import backfill_semantic_artifacts


def test_backfill_semantic_artifacts_returns_counts() -> None:
    out = backfill_semantic_artifacts(
        repo="acme/widgets",
        prompt_id="reviewer_rerank",
        since="2026-01-01T00:00:00Z",
        dry_run=True,
    )
    assert out["repo"] == "acme/widgets"
    assert out["prompt_id"] == "reviewer_rerank"
    assert out["dry_run"] is True
