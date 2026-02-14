from sdlc_core.store.artifact_index import ArtifactIndexRow, ArtifactIndexStore


def test_artifact_index_append_and_filter(tmp_path) -> None:
    idx = ArtifactIndexStore(path=tmp_path / "artifact_index.jsonl")
    idx.append(
        ArtifactIndexRow(
            artifact_id="a1",
            artifact_type="route_result",
            artifact_version="v2",
            relative_path="artifacts/route_result/a1.json",
            content_sha256="abc",
            cache_key="k1",
        )
    )
    idx.append(
        ArtifactIndexRow(
            artifact_id="a2",
            artifact_type="truth_label",
            artifact_version="v2",
            relative_path="artifacts/truth_label/a2.json",
            content_sha256="def",
            cache_key=None,
        )
    )
    rows = idx.list_rows(artifact_type="route_result")
    assert [r.artifact_id for r in rows] == ["a1"]
