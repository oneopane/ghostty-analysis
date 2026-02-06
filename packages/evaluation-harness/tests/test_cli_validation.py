from __future__ import annotations

from evaluation_harness.cli.app import app
from typer.testing import CliRunner


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
            "--baseline",
            "stewards",
        ],
    )

    assert result.exit_code != 0
    assert "--config is required when baseline includes stewards" in result.output
    assert "Traceback" not in result.output


def test_run_rejects_unknown_baseline_without_traceback() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "--repo",
            "acme/widgets",
            "--pr",
            "1",
            "--baseline",
            "unknown",
        ],
    )

    assert result.exit_code != 0
    assert "unknown baseline(s): unknown" in result.output
    assert "Traceback" not in result.output
