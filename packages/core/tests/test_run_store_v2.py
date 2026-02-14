from datetime import datetime, timezone

from sdlc_core.store.run_store import FileRunStore
from sdlc_core.types.run import RunManifest


def test_run_store_roundtrip_manifest(tmp_path) -> None:
    store = FileRunStore(root=tmp_path)
    manifest = RunManifest(
        run_id="r1",
        run_kind="evaluation",
        generated_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        repo="acme/widgets",
        task_id="reviewer_routing",
        routers=["mentions", "llm_rerank"],
        produced_artifact_refs=["artifact://route_result/a1"],
        db_max_event_occurred_at="2026-01-31T00:00:00Z",
        db_max_watermark_updated_at="2026-02-01T00:00:00Z",
    )
    path = store.write_run_manifest(rel_path="run_manifest.json", manifest=manifest)
    loaded = store.read_run_manifest(rel_path="run_manifest.json")

    assert path.exists()
    assert loaded is not None
    assert loaded.task_id == "reviewer_routing"
