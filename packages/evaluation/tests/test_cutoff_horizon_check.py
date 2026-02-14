from evaluation_harness.cli.app import app
from typer.testing import CliRunner

from .fixtures.build_min_db import build_min_db


def test_cutoff_horizon_check_returns_pass_or_fail(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "cutoff",
            "--repo",
            db.repo,
            "--cutoff",
            "1999-01-01T00:00:00Z",
            "--data-dir",
            str(db.data_dir),
        ],
    )
    assert result.exit_code == 0
    assert "pass" in result.output.lower()
