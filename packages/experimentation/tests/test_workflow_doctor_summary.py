from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import typer
from typer.testing import CliRunner

import experimentation.unified_experiment as unified_experiment
import experimentation.workflow_doctor as workflow_doctor


def _build_app() -> typer.Typer:
    app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)
    # Mirror the unified CLI shape so command parsing matches production.
    app.add_typer(unified_experiment.cohort_app, name="cohort")
    app.add_typer(unified_experiment.experiment_app, name="experiment")
    app.add_typer(unified_experiment.profile_app, name="profile")
    app.command("doctor")(unified_experiment.doctor)
    return app


def _seed_min_db(
    *, data_dir: Path, repo: str = "acme/widgets", pr_number: int = 1
) -> Path:
    owner, name = repo.split("/", 1)
    db_path = data_dir / "github" / owner / name / "history.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "create table repos (id integer primary key, full_name text not null)"
        )
        conn.execute(
            "create table pull_requests (id integer primary key, repo_id integer, number integer, created_at text)"
        )
        conn.execute(
            "create table events (id integer primary key, repo_id integer, occurred_at text, actor_id integer, event_type text, subject_type text, subject_id integer)"
        )
        conn.execute(
            "create table reviews (id integer primary key, repo_id integer, pull_request_id integer, state text)"
        )

        conn.execute("insert into repos (id, full_name) values (1, ?)", (repo,))
        conn.execute(
            "insert into pull_requests (id, repo_id, number, created_at) values (100, 1, ?, ?)",
            (int(pr_number), "2024-01-01 00:00:00"),
        )
        conn.execute(
            "insert into events (id, repo_id, occurred_at, actor_id, event_type, subject_type, subject_id) values (200, 1, ?, 10, 'pull_request.merged', 'pull_request', 100)",
            ("2024-01-02 00:00:00",),
        )
        conn.execute(
            "insert into reviews (id, repo_id, pull_request_id, state) values (300, 1, 100, 'APPROVED')"
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


class _FakeSnapshot:
    def __init__(self, *, base_sha: str | None) -> None:
        self.base_sha = base_sha


class _FakeHistoryReader:
    def __init__(self, *, repo_full_name: str, data_dir: str) -> None:
        self.repo_full_name = repo_full_name
        self.data_dir = data_dir

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False

    def pull_request_snapshot(self, *, number: int, as_of):  # type: ignore[no-untyped-def]
        return _FakeSnapshot(base_sha="deadbeef")


def test_doctor_writes_doctor_summary_json(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    repo = "acme/widgets"
    data_dir = tmp_path / "data"
    _seed_min_db(data_dir=data_dir, repo=repo, pr_number=1)

    # Provide pinned CODEOWNERS as-of base sha.
    codeowners_path = (
        data_dir
        / "github"
        / "acme"
        / "widgets"
        / "repo_artifacts"
        / "deadbeef"
        / ".github"
        / "CODEOWNERS"
    )
    codeowners_path.parent.mkdir(parents=True, exist_ok=True)
    codeowners_path.write_text("* @alice\n", encoding="utf-8")

    monkeypatch.setattr(workflow_doctor, "HistoryReader", _FakeHistoryReader)

    runner = CliRunner()
    res = runner.invoke(
        _build_app(),
        [
            "doctor",
            "--repo",
            repo,
            "--data-dir",
            str(data_dir),
            "--pr",
            "1",
        ],
    )
    assert res.exit_code == 0, res.output

    out_path = None
    plan_path = None
    for line in res.output.splitlines():
        if line.startswith("doctor_summary "):
            out_path = line.split(" ", 1)[1].strip()
        if line.startswith("pinned_artifacts_plan "):
            plan_path = line.split(" ", 1)[1].strip()
    assert out_path is not None
    assert plan_path is not None
    p = Path(out_path)
    assert p.exists()

    plan = Path(plan_path)
    assert plan.exists()

    payload = json.loads(p.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["kind"] == "doctor_summary"
    assert payload["repo"] == repo
    assert payload["checks"]["issues"] == 0
    assert payload["checks"]["codeowners"]["pass"] is True
    assert payload["checks"]["truth"]["approval_ready"] is True

    plan_payload = json.loads(plan.read_text(encoding="utf-8"))
    assert plan_payload["schema_version"] == 1
    assert plan_payload["kind"] == "pinned_artifacts_plan"
    assert plan_payload["repo"] == repo
    assert plan_payload["counts"]["pr_count"] == 1
    assert plan_payload["counts"]["codeowners_present_pr_count"] == 1


def test_doctor_strict_still_writes_summary_on_failure(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    repo = "acme/widgets"
    data_dir = tmp_path / "data"
    _seed_min_db(data_dir=data_dir, repo=repo, pr_number=1)

    monkeypatch.setattr(workflow_doctor, "HistoryReader", _FakeHistoryReader)

    runner = CliRunner()
    res = runner.invoke(
        _build_app(),
        [
            "doctor",
            "--repo",
            repo,
            "--data-dir",
            str(data_dir),
            "--pr",
            "1",
            "--strict",
        ],
    )
    assert res.exit_code == 1

    out_path = None
    plan_path = None
    for line in res.output.splitlines():
        if line.startswith("doctor_summary "):
            out_path = line.split(" ", 1)[1].strip()
        if line.startswith("pinned_artifacts_plan "):
            plan_path = line.split(" ", 1)[1].strip()
    assert out_path is not None
    assert plan_path is not None
    p = Path(out_path)
    assert p.exists()

    plan = Path(plan_path)
    assert plan.exists()

    payload = json.loads(p.read_text(encoding="utf-8"))
    assert payload["checks"]["issues"] > 0
    assert payload["checks"]["codeowners"]["pass"] is False

    plan_payload = json.loads(plan.read_text(encoding="utf-8"))
    assert plan_payload["counts"]["codeowners_present_pr_count"] == 0
