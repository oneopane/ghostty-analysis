from __future__ import annotations

import json
from pathlib import Path

import typer
from typer.testing import CliRunner

import experimentation.unified_experiment as unified_experiment


def _build_app() -> typer.Typer:
    app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)
    app.add_typer(unified_experiment.experiment_app, name="experiment")
    return app


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )


def test_index_all_skips_incomplete_by_default(tmp_path: Path) -> None:
    repo = "acme/widgets"
    data_dir = tmp_path / "data"
    base = data_dir / "github" / "acme" / "widgets" / "eval"

    run_complete = base / "run-complete"
    run_incomplete = base / "run-incomplete"
    run_complete.mkdir(parents=True, exist_ok=True)
    run_incomplete.mkdir(parents=True, exist_ok=True)

    # Complete run: per_pr + report + manifest.
    (run_complete / "per_pr.jsonl").write_text(
        json.dumps(
            {
                "repo": repo,
                "run_id": "run-complete",
                "pr_number": 1,
                "cutoff": "2024-01-01T00:00:00Z",
                "truth_status": "observed",
                "truth": {"primary_policy": "p", "policies": {}},
                "gates": {},
                "routers": {"mentions": {}},
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(run_complete / "report.json", {"kind": "eval_report", "version": "v0"})
    _write_json(
        run_complete / "manifest.json",
        {
            "kind": "eval_manifest",
            "version": "v0",
            "config": {
                "defaults": {"cutoff_policy": "created_at", "llm_mode": "replay"}
            },
            "pr_numbers": [1],
            "pr_cutoffs": {"1": "2024-01-01T00:00:00Z"},
        },
    )

    # Incomplete run: only per_pr.
    (run_incomplete / "per_pr.jsonl").write_text(
        json.dumps(
            {
                "repo": repo,
                "run_id": "run-incomplete",
                "pr_number": 2,
                "cutoff": "2024-01-01T00:00:00Z",
                "truth_status": "observed",
                "truth": {"primary_policy": "p", "policies": {}},
                "gates": {},
                "routers": {"mentions": {}},
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    res = runner.invoke(
        _build_app(),
        [
            "experiment",
            "index-all",
            "--repo",
            repo,
            "--data-dir",
            str(data_dir),
        ],
    )
    assert res.exit_code == 0, res.output
    assert (run_complete / "run_summary.json").exists()
    assert not (run_incomplete / "run_summary.json").exists()


def test_index_all_can_include_incomplete(tmp_path: Path) -> None:
    repo = "acme/widgets"
    data_dir = tmp_path / "data"
    base = data_dir / "github" / "acme" / "widgets" / "eval"
    run_incomplete = base / "run-incomplete"
    run_incomplete.mkdir(parents=True, exist_ok=True)
    (run_incomplete / "per_pr.jsonl").write_text(
        json.dumps(
            {
                "repo": repo,
                "run_id": "run-incomplete",
                "pr_number": 2,
                "cutoff": "2024-01-01T00:00:00Z",
                "truth_status": "observed",
                "truth": {"primary_policy": "p", "policies": {}},
                "gates": {},
                "routers": {"mentions": {}},
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    res = runner.invoke(
        _build_app(),
        [
            "experiment",
            "index-all",
            "--repo",
            repo,
            "--data-dir",
            str(data_dir),
            "--include-incomplete",
        ],
    )
    assert res.exit_code == 0, res.output
