from __future__ import annotations

import json

from evaluation_harness.compare_summary import write_compare_summary
from evaluation_harness.config import EvalRunConfig
from evaluation_harness.runner import run_streaming_eval
from repo_routing.registry import RouterSpec

from .fixtures.build_min_db import build_min_db


def test_compare_summary_writes_artifact(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)

    cfg_a = EvalRunConfig(repo=db.repo, data_dir=str(db.data_dir), run_id="run-a")
    cfg_b = EvalRunConfig(repo=db.repo, data_dir=str(db.data_dir), run_id="run-b")
    run_streaming_eval(
        cfg=cfg_a,
        pr_numbers=[db.pr_number],
        router_specs=[
            RouterSpec(type="builtin", name="mentions"),
            RouterSpec(type="builtin", name="popularity"),
        ],
    )
    run_streaming_eval(
        cfg=cfg_b,
        pr_numbers=[db.pr_number],
        router_specs=[
            RouterSpec(type="builtin", name="mentions"),
            RouterSpec(type="builtin", name="popularity"),
        ],
    )

    out = write_compare_summary(
        repo=db.repo,
        data_dir=str(db.data_dir),
        baseline_run_id="run-a",
        candidate_run_id="run-b",
    )
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["kind"] == "compare_summary"
    assert payload["repo"] == db.repo
    assert payload["baseline"]["run_id"] == "run-a"
    assert payload["candidate"]["run_id"] == "run-b"
    for key in (
        "compatibility",
        "ranked_deltas",
        "top_regressed_slices",
        "top_regressed_examples",
        "gate_deltas",
        "drill",
    ):
        assert key in payload
