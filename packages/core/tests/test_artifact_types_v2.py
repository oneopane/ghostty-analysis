from datetime import datetime, timezone

from sdlc_core.types.artifact import (
    ArtifactEntityRef,
    ArtifactHeader,
    ArtifactRecord,
    VersionKey,
)


def test_artifact_record_has_stable_artifact_id() -> None:
    header = ArtifactHeader(
        artifact_type="route_result",
        artifact_version="v2",
        entity=ArtifactEntityRef(
            repo="acme/widgets",
            entity_type="pull_request",
            entity_id="42",
            entity_version="sha:abc123",
        ),
        cutoff=datetime(2026, 2, 1, tzinfo=timezone.utc),
        created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        code_version="deadbeef",
        config_hash="cfg123",
        version_key=VersionKey(
            operator_id="router.llm_rerank",
            operator_version="v2",
            schema_version="v2",
        ),
        input_artifact_refs=[],
    )
    rec = ArtifactRecord(header=header, payload={"top_k": 5})
    assert rec.artifact_id.startswith("route_result__acme_widgets__pull_request__42__")
