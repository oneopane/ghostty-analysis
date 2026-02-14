from datetime import datetime, timezone

from sdlc_core.store.artifact_store import FileArtifactStore
from sdlc_core.types.artifact import ArtifactEntityRef, ArtifactHeader, ArtifactRecord, VersionKey


def test_file_artifact_store_write_and_cache_lookup(tmp_path) -> None:
    store = FileArtifactStore(root=tmp_path)
    record = ArtifactRecord(
        header=ArtifactHeader(
            artifact_type="llm_extract",
            artifact_version="v1",
            entity=ArtifactEntityRef(repo="acme/widgets", entity_type="comment", entity_id="99"),
            cutoff=datetime(2026, 2, 1, tzinfo=timezone.utc),
            created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
            code_version="deadbeef",
            config_hash="cfg",
            version_key=VersionKey(operator_id="extractor", operator_version="v1", schema_version="v1"),
            input_artifact_refs=[],
        ),
        payload={"label": "out_of_scope"},
    )

    ref = store.write_artifact(record=record, cache_key="comment:99:v1")
    hit = store.find_cached(cache_key="comment:99:v1")

    assert hit is not None
    assert hit.artifact_id == ref.artifact_id
