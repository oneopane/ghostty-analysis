from __future__ import annotations

import experimentation.unified_experiment as experimentation_unified
import repo_cli.unified_experiment as repo_cli_unified
from repo_cli.cli import app
from typer.testing import CliRunner


def test_repo_cli_help_lists_unified_groups() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "cohort" in result.output
    assert "experiment" in result.output
    assert "profile" in result.output
    assert "doctor" in result.output


def test_unified_experiment_shim_exposes_experimentation_module() -> None:
    assert repo_cli_unified.experiment_app is experimentation_unified.experiment_app
    assert repo_cli_unified.cohort_app is experimentation_unified.cohort_app
    assert repo_cli_unified.profile_app is experimentation_unified.profile_app


def test_repo_cli_experiment_help_is_wired() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["experiment", "--help"])
    assert result.exit_code == 0, result.output
    assert "run" in result.output
    assert "diff" in result.output
