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


def _write_run_summary(
    run_dir: Path, *, promote: bool | None, eligible: bool | None
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "schema_version": 1,
        "kind": "run_summary",
        "repo": "acme/widgets",
        "run_id": "run-x",
        "watermark": {},
        "inputs": {"cohort_hash": None, "experiment_spec_hash": None, "routers": []},
        "counts": {"pr_count": 0, "per_pr_row_count": 0},
        "artifacts": {},
        "hashes": {},
        "headline_metrics": {},
        "gates": {
            "truth_coverage_counts": {},
            "gate_correlation": None,
            "quality_gates": {"all_pass": True, "gates": {}, "thresholds": {}},
            "promotion_evaluation": None,
            "warnings": [],
        },
        "drill": {},
    }
    if eligible is not None or promote is not None:
        promo: dict[str, object] = {}
        if eligible is not None:
            promo["eligible"] = eligible
        if promote is not None:
            promo["promote"] = promote
        payload["gates"]["promotion_evaluation"] = promo  # type: ignore[index]
    (run_dir / "run_summary.json").write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    (run_dir / "report.json").write_text("{}\n", encoding="utf-8")
    (run_dir / "per_pr.jsonl").write_text("", encoding="utf-8")
    (run_dir / "manifest.json").write_text("{}\n", encoding="utf-8")


def test_promote_exits_zero_when_promote_true(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    run_dir = data_dir / "github" / "acme" / "widgets" / "eval" / "run-x"
    _write_run_summary(run_dir, promote=True, eligible=True)

    runner = CliRunner()
    res = runner.invoke(
        _build_app(),
        [
            "experiment",
            "promote",
            "--repo",
            "acme/widgets",
            "--run-id",
            "run-x",
            "--data-dir",
            str(data_dir),
        ],
    )
    assert res.exit_code == 0, res.output
    assert (run_dir / "promotion_summary.json").exists()


def test_promote_exits_two_when_ineligible(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    run_dir = data_dir / "github" / "acme" / "widgets" / "eval" / "run-x"
    _write_run_summary(run_dir, promote=None, eligible=False)

    runner = CliRunner()
    res = runner.invoke(
        _build_app(),
        [
            "experiment",
            "promote",
            "--repo",
            "acme/widgets",
            "--run-id",
            "run-x",
            "--data-dir",
            str(data_dir),
        ],
    )
    assert res.exit_code == 2
    assert (run_dir / "promotion_summary.json").exists()
