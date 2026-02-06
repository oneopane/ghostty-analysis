from __future__ import annotations

import json

from evaluation_harness.config import EvalRunConfig
from evaluation_harness.runner import run_streaming_eval
from repo_routing.registry import RouterSpec, router_id_for_spec

from .fixtures.build_min_db import build_min_db


def test_runner_import_path_router_writes_route_and_features(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)
    cfg = EvalRunConfig(repo=db.repo, data_dir=str(db.data_dir), run_id="run-import")

    spec = RouterSpec(
        type="import_path",
        name="example-llm",
        import_path="repo_routing.examples.llm_router_example:create_router",
    )
    rid = router_id_for_spec(spec)

    res = run_streaming_eval(cfg=cfg, pr_numbers=[db.pr_number], router_specs=[spec])

    pr_dir = res.run_dir / "prs" / str(db.pr_number)
    assert (pr_dir / "routes" / f"{rid}.json").exists()
    assert (pr_dir / "features" / f"{rid}.json").exists()

    row = json.loads((res.run_dir / "per_pr.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert rid in row["routers"]
