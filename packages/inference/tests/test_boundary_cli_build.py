from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from repo_routing.boundary.paths import boundary_manifest_path, boundary_model_path
from repo_routing.cli.app import app
from repo_routing.time import cutoff_key_utc, parse_dt_utc
from typer.testing import CliRunner


def _seed_boundary_db(base_dir: Path) -> str:
    repo = "acme/widgets"
    owner, name = repo.split("/", 1)
    db_path = base_dir / "github" / owner / name / "history.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("create table repos (id integer primary key, full_name text not null)")
        conn.execute(
            """
            create table pull_requests (
                id integer primary key,
                repo_id integer,
                number integer,
                created_at text
            )
            """
        )
        conn.execute(
            """
            create table pull_request_files (
                repo_id integer,
                pull_request_id integer,
                head_sha text,
                path text,
                status text,
                additions integer,
                deletions integer,
                changes integer
            )
            """
        )

        conn.execute("insert into repos (id, full_name) values (1, ?)", (repo,))
        conn.execute(
            "insert into pull_requests (id, repo_id, number, created_at) values (101, 1, 1, '2024-01-10 00:00:00')"
        )
        conn.execute(
            """
            insert into pull_request_files
            (repo_id, pull_request_id, head_sha, path, status, additions, deletions, changes)
            values (1, 101, 'h1', 'src/a.py', 'modified', 1, 1, 2)
            """
        )

        conn.commit()
    finally:
        conn.close()

    return repo


def test_boundary_build_cli_writes_artifacts(tmp_path: Path) -> None:
    repo = _seed_boundary_db(tmp_path / "data")
    runner = CliRunner()

    as_of = "2024-01-15T00:00:00Z"
    result = runner.invoke(
        app,
        [
            "boundary",
            "build",
            "--repo",
            repo,
            "--as-of",
            as_of,
            "--data-dir",
            str(tmp_path / "data"),
        ],
    )

    assert result.exit_code == 0, result.output

    cutoff = parse_dt_utc(as_of)
    assert cutoff is not None
    ck = cutoff_key_utc(cutoff)

    model_path = boundary_model_path(
        repo_full_name=repo,
        data_dir=tmp_path / "data",
        strategy_id="hybrid_path_cochange.v1",
        cutoff_key=ck,
    )
    manifest_path = boundary_manifest_path(
        repo_full_name=repo,
        data_dir=tmp_path / "data",
        strategy_id="hybrid_path_cochange.v1",
        cutoff_key=ck,
    )
    assert model_path.exists()
    assert manifest_path.exists()

    model_payload = json.loads(model_path.read_text(encoding="utf-8"))
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert model_payload["strategy_id"] == "hybrid_path_cochange.v1"
    assert manifest_payload["strategy_version"] == "v1"


def test_boundary_build_cli_parser_fallback_and_strict_mode(tmp_path: Path) -> None:
    repo = _seed_boundary_db(tmp_path / "data")
    runner = CliRunner()

    as_of = "2024-01-15T00:00:00Z"
    ok = runner.invoke(
        app,
        [
            "boundary",
            "build",
            "--repo",
            repo,
            "--as-of",
            as_of,
            "--data-dir",
            str(tmp_path / "data"),
            "--parser-enabled",
            "--parser-snapshot-root",
            str(tmp_path / "missing"),
        ],
    )
    assert ok.exit_code == 0, ok.output

    cutoff = parse_dt_utc(as_of)
    assert cutoff is not None
    ck = cutoff_key_utc(cutoff)
    manifest_path = boundary_manifest_path(
        repo_full_name=repo,
        data_dir=tmp_path / "data",
        strategy_id="hybrid_path_cochange.v1",
        cutoff_key=ck,
    )
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    parser_cov = manifest_payload["parser_coverage"]
    assert parser_cov["enabled"] is True
    assert "parser_snapshot_missing" in parser_cov["diagnostics"]

    strict = runner.invoke(
        app,
        [
            "boundary",
            "build",
            "--repo",
            repo,
            "--as-of",
            as_of,
            "--data-dir",
            str(tmp_path / "data"),
            "--parser-enabled",
            "--parser-strict",
            "--parser-snapshot-root",
            str(tmp_path / "missing"),
        ],
    )
    assert strict.exit_code != 0
    assert strict.exception is not None
    assert "snapshot root missing" in str(strict.exception)
