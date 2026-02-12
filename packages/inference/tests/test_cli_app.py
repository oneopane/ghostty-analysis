from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from repo_routing.time import cutoff_key_utc, parse_dt_utc

import repo_routing.cli.app as cli_app_module
from repo_routing.boundary.models import MembershipMode
from repo_routing.boundary.pipeline import write_boundary_model_artifacts
from repo_routing.cli.app import app
from typer.testing import CliRunner


def _seed_db(base_dir: Path) -> tuple[str, Path]:
    repo = "acme/widgets"
    owner, name = repo.split("/", 1)
    db_path = base_dir / "github" / owner / name / "history.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "create table repos (id integer primary key, full_name text not null)"
        )
        conn.execute(
            "create table users (id integer primary key, login text, type text)"
        )
        conn.execute(
            "create table events (id integer primary key, occurred_at text)"
        )
        conn.execute(
            """
            create table pull_requests (
                id integer primary key,
                repo_id integer,
                number integer,
                issue_id integer,
                user_id integer,
                created_at text,
                title text,
                body text,
                base_sha text,
                base_ref text
            )
            """
        )
        conn.execute(
            """
            create table pull_request_head_intervals (
                id integer primary key,
                pull_request_id integer,
                head_sha text,
                head_ref text,
                start_event_id integer,
                end_event_id integer
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
        conn.execute(
            """
            create table reviews (
                id integer primary key,
                repo_id integer,
                pull_request_id integer,
                user_id integer,
                state text,
                submitted_at text
            )
            """
        )
        conn.execute(
            """
            create table comments (
                id integer primary key,
                repo_id integer,
                pull_request_id integer,
                user_id integer,
                created_at text,
                path text,
                comment_type text,
                review_id integer
            )
            """
        )
        conn.execute(
            """
            create table pull_request_review_request_intervals (
                id integer primary key,
                pull_request_id integer,
                reviewer_type text,
                reviewer_id integer,
                start_event_id integer,
                end_event_id integer
            )
            """
        )

        conn.execute("insert into repos (id, full_name) values (1, ?)", (repo,))
        conn.execute("insert into users (id, login, type) values (1, 'alice', null)")
        conn.execute("insert into users (id, login, type) values (2, 'bob', null)")

        conn.execute(
            """
            insert into pull_requests
            (id, repo_id, number, issue_id, user_id, created_at, title, body, base_sha, base_ref)
            values
            (101, 1, 1, null, 1, '2024-01-10 00:00:00', 'Add feature',
             'Issue: #123\nAI: no\nProvenance: human\ncc @bob', 'base1', 'main')
            """
        )

        conn.execute(
            "insert into events (id, occurred_at) values (1, '2024-01-01 00:00:00')"
        )
        conn.execute(
            "insert into events (id, occurred_at) values (2, '2024-01-05 12:00:00')"
        )

        conn.execute(
            """
            insert into pull_request_head_intervals
            (id, pull_request_id, head_sha, head_ref, start_event_id, end_event_id)
            values
            (1, 101, 'head1', 'main', 1, null)
            """
        )

        conn.execute(
            """
            insert into pull_request_files
            (repo_id, pull_request_id, head_sha, path, status, additions, deletions, changes)
            values
            (1, 101, 'head1', 'src/app.py', 'modified', 10, 2, 12)
            """
        )

        conn.execute(
            """
            insert into reviews
            (id, repo_id, pull_request_id, user_id, state, submitted_at)
            values
            (201, 1, 101, 2, 'APPROVED', '2024-01-05 12:00:00')
            """
        )

        conn.execute(
            """
            insert into comments
            (id, repo_id, pull_request_id, user_id, created_at, path, comment_type, review_id)
            values
            (301, 1, 101, 2, '2024-01-05 12:00:00', null, 'issue', null)
            """
        )

        conn.commit()
    finally:
        conn.close()

    return repo, base_dir


def _write_stewards_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "version": "v0",
                "feature_version": "v0",
                "candidate_pool": {
                    "lookback_days": 180,
                    "exclude_author": True,
                    "exclude_bots": True,
                },
                "decay": {"half_life_days": 30, "lookback_days": 180},
                "event_weights": {
                    "review_submitted": 1.0,
                    "review_comment_created": 0.4,
                    "comment_created": 0.2,
                },
                "weights": {"boundary_overlap_activity": 1.0, "activity_total": 0.2},
                "filters": {"min_activity_total": 0.0},
                "thresholds": {
                    "confidence_high_margin": 0.1,
                    "confidence_med_margin": 0.05,
                },
                "labels": {"include_boundary_labels": False},
            }
        ),
        encoding="utf-8",
    )
    return config_path


def _write_boundary_for_cutoff(repo: str, data_dir: Path, cutoff: str) -> None:
    cutoff_dt = parse_dt_utc(cutoff)
    assert cutoff_dt is not None
    write_boundary_model_artifacts(
        repo_full_name=repo,
        cutoff_utc=cutoff_dt,
        cutoff_key=cutoff_key_utc(cutoff_dt),
        data_dir=data_dir,
        membership_mode=MembershipMode.MIXED,
    )


def test_build_artifacts_stewards_implicit_cutoff_uses_utc(tmp_path: Path) -> None:
    repo, data_dir = _seed_db(tmp_path / "data")
    config_path = _write_stewards_config(tmp_path)
    _write_boundary_for_cutoff(repo, data_dir, "2024-01-10T00:00:00Z")
    runner = CliRunner()

    run_id = "run-stewards-implicit"
    result = runner.invoke(
        app,
        [
            "build-artifacts",
            "--repo",
            repo,
            "--run-id",
            run_id,
            "--pr",
            "1",
            "--baseline",
            "stewards",
            "--config",
            str(config_path),
            "--data-dir",
            str(data_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    pr_dir = (
        data_dir / "github" / "acme" / "widgets" / "eval" / run_id / "prs" / "1"
    )
    assert (pr_dir / "snapshot.json").exists()

    out = pr_dir / "routes" / "stewards.json"
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["result"]["as_of"] == "2024-01-10T00:00:00Z"


def test_route_accepts_naive_as_of_and_treats_it_as_utc(tmp_path: Path) -> None:
    repo, data_dir = _seed_db(tmp_path / "data")
    config_path = _write_stewards_config(tmp_path)
    _write_boundary_for_cutoff(repo, data_dir, "2024-01-10T00:00:00Z")
    runner = CliRunner()

    run_id = "run-route-naive"
    result = runner.invoke(
        app,
        [
            "route",
            "--repo",
            repo,
            "--pr-number",
            "1",
            "--baseline",
            "stewards",
            "--config",
            str(config_path),
            "--run-id",
            run_id,
            "--as-of",
            "2024-01-10T00:00:00",
            "--data-dir",
            str(data_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    out = (
        data_dir
        / "github"
        / "acme"
        / "widgets"
        / "eval"
        / run_id
        / "prs"
        / "1"
        / "routes"
        / "stewards.json"
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["result"]["as_of"] == "2024-01-10T00:00:00Z"


def test_route_missing_stewards_config_returns_clean_error() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "route",
            "--repo",
            "acme/widgets",
            "--pr-number",
            "1",
            "--baseline",
            "stewards",
            "--run-id",
            "x",
            "--as-of",
            "2024-01-10T00:00:00Z",
        ],
    )

    assert result.exit_code != 0
    assert "--config is required when baseline includes stewards" in result.output
    assert "Traceback" not in result.output


def test_build_artifacts_does_not_write_partial_files_on_route_failure(
    tmp_path: Path, monkeypatch
) -> None:
    repo, data_dir = _seed_db(tmp_path / "data")
    runner = CliRunner()

    original = cli_app_module.build_route_artifact

    def _boom_on_popularity(**kwargs):  # type: ignore[no-untyped-def]
        if kwargs.get("baseline") == "popularity":
            raise RuntimeError("forced route failure")
        return original(**kwargs)

    monkeypatch.setattr(cli_app_module, "build_route_artifact", _boom_on_popularity)

    run_id = "run-no-partials"
    result = runner.invoke(
        app,
        [
            "build-artifacts",
            "--repo",
            repo,
            "--run-id",
            run_id,
            "--pr",
            "1",
            "--baseline",
            "mentions",
            "--baseline",
            "popularity",
            "--as-of",
            "2024-01-10T00:00:00Z",
            "--data-dir",
            str(data_dir),
        ],
    )

    assert result.exit_code != 0

    pr_dir = (
        data_dir
        / "github"
        / "acme"
        / "widgets"
        / "eval"
        / run_id
        / "prs"
        / "1"
    )
    assert not (pr_dir / "snapshot.json").exists()
    assert not (pr_dir / "routes" / "mentions.json").exists()


def test_boundary_subcommand_is_available() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["boundary", "--help"])

    assert result.exit_code == 0
    assert "build" in result.output
