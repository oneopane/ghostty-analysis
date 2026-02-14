from __future__ import annotations

from evaluation_harness.cli.app import app
from evaluation_harness.config import EvalRunConfig
from evaluation_harness.runner import run_streaming_eval
from repo_routing.registry import RouterSpec
from typer.testing import CliRunner

from .fixtures.build_min_db import build_min_db


def test_run_requires_config_for_stewards_without_traceback() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "--repo",
            "acme/widgets",
            "--pr",
            "1",
            "--router",
            "stewards",
        ],
    )

    assert result.exit_code != 0
    assert "--config is required when router includes stewards" in result.output
    assert "Traceback" not in result.output


def test_run_rejects_unknown_router_without_traceback() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "--repo",
            "acme/widgets",
            "--pr",
            "1",
            "--router",
            "unknown",
        ],
    )

    assert result.exit_code != 0
    assert "unknown router(s): unknown" in result.output
    assert "Traceback" not in result.output


def test_explain_supports_policy_selection(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)
    cfg = EvalRunConfig(repo=db.repo, data_dir=str(db.data_dir), run_id="run-explain-policy")
    run_streaming_eval(
        cfg=cfg,
        pr_numbers=[db.pr_number],
        router_specs=[RouterSpec(type="builtin", name="mentions")],
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "explain",
            "--repo",
            db.repo,
            "--run-id",
            "run-explain-policy",
            "--pr",
            str(db.pr_number),
            "--router",
            "mentions",
            "--policy",
            "first_response_v1",
            "--data-dir",
            str(db.data_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "first_response_v1" in result.output
