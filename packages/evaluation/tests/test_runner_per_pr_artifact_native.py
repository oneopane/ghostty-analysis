import json

from evaluation_harness.config import EvalRunConfig
from evaluation_harness.runner import run_streaming_eval
from repo_routing.registry import RouterSpec

from .fixtures.build_min_db import build_min_db


def test_runner_writes_artifact_index_with_truth_and_routes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)
    cfg = EvalRunConfig(repo=db.repo, data_dir=str(db.data_dir), run_id="artifact-native")
    run_streaming_eval(
        cfg=cfg,
        pr_numbers=[db.pr_number],
        router_specs=[RouterSpec(type="builtin", name="mentions")],
    )

    idx = db.data_dir / "github" / "acme" / "widgets" / "eval" / "artifact-native" / "artifact_index.jsonl"
    rows = [json.loads(line) for line in idx.read_text(encoding="utf-8").splitlines() if line.strip()]
    kinds = {r["artifact_type"] for r in rows}
    assert "route_result" in kinds
    assert "truth_label" in kinds
