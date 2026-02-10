from __future__ import annotations

import json
from datetime import timedelta

from evaluation_harness.cli.app import app
from evaluation_harness.config import EvalDefaults, EvalRunConfig
from evaluation_harness.paths import eval_manifest_path, eval_report_json_path
from evaluation_harness.runner import run_streaming_eval
from repo_routing.registry import RouterSpec
from typer.testing import CliRunner

from .fixtures.build_min_db import build_min_db


def test_end_to_end_eval_run(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)
    runner = CliRunner()

    r = runner.invoke(
        app,
        [
            "run",
            "--repo",
            db.repo,
            "--data-dir",
            str(db.data_dir),
            "--pr",
            str(db.pr_number),
            "--baseline",
            "mentions",
            "--baseline",
            "popularity",
        ],
    )
    assert r.exit_code == 0, r.output

    # Pull run_id out of output: "run_dir <path>".
    run_dir = None
    for line in r.output.splitlines():
        if "run_dir" in line:
            run_dir = line.split(" ")[-1].strip()
            break
    assert run_dir is not None

    run_id = run_dir.rstrip("/").split("/")[-1]
    assert eval_manifest_path(
        repo_full_name=db.repo, data_dir=db.data_dir, run_id=run_id
    ).exists()
    assert eval_report_json_path(
        repo_full_name=db.repo, data_dir=db.data_dir, run_id=run_id
    ).exists()


def test_truth_window_in_manifest_matches_effective_diagnostics(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)
    cfg = EvalRunConfig(
        repo=db.repo,
        data_dir=str(db.data_dir),
        run_id="run-truth-window",
        defaults=EvalDefaults(
            truth_window=timedelta(minutes=10),
            truth_include_review_comments=False,
        ),
    )
    res = run_streaming_eval(
        cfg=cfg,
        pr_numbers=[db.pr_number],
        router_specs=[RouterSpec(type="builtin", name="mentions")],
    )

    row = json.loads((res.run_dir / "per_pr.jsonl").read_text(encoding="utf-8").splitlines()[0])
    manifest = json.loads((res.run_dir / "manifest.json").read_text(encoding="utf-8"))

    diag = row["truth_diagnostics"]
    assert row["truth_status"] == "no_post_cutoff_response"
    assert diag["include_review_comments"] is False
    assert manifest["truth"]["effective_window_seconds"] == 600
    assert manifest["truth"]["include_review_comments"] is False
