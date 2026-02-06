from __future__ import annotations

import json

from evaluation_harness.config import EvalRunConfig
from evaluation_harness.runner import run_streaming_eval
from repo_routing.registry import RouterSpec

from .fixtures.build_min_db import build_min_db


def test_runner_writes_router_artifacts_and_routers_key(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)
    cfg = EvalRunConfig(repo=db.repo, data_dir=str(db.data_dir), run_id="run-routers")

    res = run_streaming_eval(
        cfg=cfg,
        pr_numbers=[db.pr_number],
        router_specs=[RouterSpec(type="builtin", name="mentions")],
    )

    pr_dir = res.run_dir / "prs" / str(db.pr_number)
    assert (pr_dir / "snapshot.json").exists()
    assert (pr_dir / "inputs.json").exists()
    assert (pr_dir / "routes" / "mentions.json").exists()

    per_pr = (res.run_dir / "per_pr.jsonl").read_text(encoding="utf-8").strip().splitlines()
    row = json.loads(per_pr[0])
    assert "routers" in row
    assert "mentions" in row["routers"]
