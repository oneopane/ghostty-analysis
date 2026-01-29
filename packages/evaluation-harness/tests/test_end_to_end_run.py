from __future__ import annotations

from evaluation_harness.cli.app import app
from evaluation_harness.paths import eval_manifest_path, eval_report_json_path
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
