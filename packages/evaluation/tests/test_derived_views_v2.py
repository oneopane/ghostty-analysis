from evaluation_harness.config import EvalRunConfig
from evaluation_harness.runner import run_streaming_eval
from repo_routing.registry import RouterSpec

from .fixtures.build_min_db import build_min_db


def test_emit_materializes_report_and_per_pr_from_artifacts(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)
    cfg = EvalRunConfig(repo=db.repo, data_dir=str(db.data_dir), run_id="derived-v2")
    res = run_streaming_eval(
        cfg=cfg,
        pr_numbers=[db.pr_number],
        router_specs=[RouterSpec(type="builtin", name="mentions")],
    )

    assert (res.run_dir / "per_pr.jsonl").exists()
    assert (res.run_dir / "report.json").exists()
