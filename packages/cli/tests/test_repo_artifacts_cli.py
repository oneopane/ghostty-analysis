from repo_cli.cli import app
from typer.testing import CliRunner


def test_repo_artifacts_group_exists() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["artifacts", "--help"])
    assert result.exit_code == 0, result.output
    assert "list" in result.output
    assert "show" in result.output


def test_repo_backfill_group_exists() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["backfill", "--help"])
    assert result.exit_code == 0, result.output
    assert "semantic" in result.output
