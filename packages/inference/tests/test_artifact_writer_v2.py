from datetime import datetime, timezone

from repo_routing.artifacts.writer import ArtifactWriter
from repo_routing.router.base import RouteResult


def test_route_write_creates_artifact_index_entry(tmp_path) -> None:
    writer = ArtifactWriter(repo="acme/widgets", data_dir=tmp_path, run_id="run-v2")
    result = RouteResult(
        repo="acme/widgets",
        pr_number=7,
        as_of=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )

    ref = writer.write_route_result_v2(router_id="mentions", result=result, meta={})

    assert ref.artifact_type == "route_result"
    idx = (
        tmp_path
        / "github"
        / "acme"
        / "widgets"
        / "eval"
        / "run-v2"
        / "artifact_index.jsonl"
    )
    assert idx.exists()
