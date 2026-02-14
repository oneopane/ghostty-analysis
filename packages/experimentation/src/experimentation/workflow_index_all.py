from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
from evaluation_harness.api import write_run_summary
from evaluation_harness.paths import repo_eval_dir
from repo_routing.runtime_defaults import DEFAULT_DATA_DIR

from .examples_index import examples_index_sqlite_path, index_run
from .workflow_helpers import _write_json


def _stable_hash(obj: object) -> str:
    data = json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _default_build_dir(*, repo: str, data_dir: str, build_id: str) -> Path:
    owner, name = repo.split("/", 1)
    return (
        Path(data_dir)
        / "github"
        / owner
        / name
        / "examples_index"
        / "builds"
        / build_id
    )


def experiment_index_all(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    data_dir: str = typer.Option(DEFAULT_DATA_DIR, help="Base directory for repo data"),
    include_incomplete: bool = typer.Option(
        False,
        "--include-incomplete",
        help="Index runs missing report/manifest if per_pr.jsonl is present",
    ),
    output_dir: str | None = typer.Option(
        None,
        help="Optional output directory for build artifacts (default: data/github/<repo>/examples_index/builds/<build_id>)",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Exit non-zero if any run fails to index",
    ),
):
    """Backfill run_summary.json and rebuild examples_index.sqlite from all run dirs."""

    eval_dir = repo_eval_dir(repo_full_name=repo, data_dir=data_dir)
    if not eval_dir.exists():
        raise typer.BadParameter(f"missing eval dir: {eval_dir}")

    run_dirs = [
        p for p in eval_dir.iterdir() if p.is_dir() and not p.name.startswith("_")
    ]
    run_dirs.sort(key=lambda p: p.name.lower())

    selected: list[Path] = []
    skipped: list[dict[str, object]] = []
    for rd in run_dirs:
        per_pr_path = rd / "per_pr.jsonl"
        report_path = rd / "report.json"
        manifest_path = rd / "manifest.json"
        has_per_pr = per_pr_path.exists()
        has_report = report_path.exists()
        has_manifest = manifest_path.exists()

        if not has_per_pr:
            skipped.append(
                {
                    "run_id": rd.name,
                    "reason": "missing per_pr.jsonl",
                }
            )
            continue
        if not include_incomplete and (not has_report or not has_manifest):
            skipped.append(
                {
                    "run_id": rd.name,
                    "reason": "missing report.json or manifest.json",
                }
            )
            continue
        selected.append(rd)

    build_id = _stable_hash(
        {
            "repo": repo,
            "data_dir": str(data_dir),
            "include_incomplete": bool(include_incomplete),
            "selected_run_ids": [p.name for p in selected],
            "schema_version": 1,
        }
    )

    build_dir = (
        Path(output_dir)
        if output_dir is not None
        else _default_build_dir(repo=repo, data_dir=data_dir, build_id=build_id)
    )
    build_dir.mkdir(parents=True, exist_ok=True)

    sqlite_path = examples_index_sqlite_path(repo=repo, data_dir=data_dir)
    results_jsonl = build_dir / "runs_index_results.jsonl"
    summary_json = build_dir / "examples_index_build_summary.json"

    indexed_runs = 0
    indexed_examples_total = 0
    run_summaries_written = 0
    errors: list[str] = []

    def write_result(obj: dict[str, object]) -> None:
        results_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with results_jsonl.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    obj, sort_keys=True, ensure_ascii=True, separators=(",", ":")
                )
                + "\n"
            )

    # Reset the results file for deterministic rebuilds.
    results_jsonl.write_text("", encoding="utf-8")

    for rd in selected:
        run_id = rd.name
        report_path = rd / "report.json"
        manifest_path = rd / "manifest.json"

        run_summary_written = False
        run_summary_error: str | None = None

        if report_path.exists() and manifest_path.exists():
            try:
                write_run_summary(repo=repo, run_id=run_id, run_dir=rd)
                run_summary_written = True
                run_summaries_written += 1
            except Exception as exc:
                run_summary_error = f"run_summary_error: {exc}"

        indexed_n = 0
        status = "indexed"
        error: str | None = None
        try:
            _, indexed_n = index_run(
                repo=repo, run_id=run_id, data_dir=data_dir, run_dir=rd
            )
            indexed_runs += 1
            indexed_examples_total += int(indexed_n)
        except Exception as exc:
            status = "error"
            error = str(exc)
            errors.append(f"{run_id}: {error}")

        write_result(
            {
                "run_id": run_id,
                "run_dir": str(rd),
                "status": status,
                "indexed_examples": int(indexed_n),
                "run_summary_written": bool(run_summary_written),
                "run_summary_error": run_summary_error,
                "error": error,
            }
        )

    for sk in skipped:
        write_result(
            {
                "run_id": sk.get("run_id"),
                "run_dir": None,
                "status": "skipped",
                "indexed_examples": 0,
                "run_summary_written": False,
                "run_summary_error": None,
                "error": sk.get("reason"),
            }
        )

    payload: dict[str, Any] = {
        "schema_version": 1,
        "kind": "examples_index_build_summary",
        "build_id": build_id,
        "generated_at": _now_iso_utc(),
        "repo": repo,
        "data_dir": str(data_dir),
        "eval_dir": str(eval_dir),
        "include_incomplete": bool(include_incomplete),
        "counts": {
            "discovered_runs": int(len(run_dirs)),
            "selected_runs": int(len(selected)),
            "skipped_runs": int(len(skipped)),
            "indexed_runs": int(indexed_runs),
            "run_summaries_written": int(run_summaries_written),
            "indexed_examples_total": int(indexed_examples_total),
            "error_runs": int(len(errors)),
        },
        "artifacts": {
            "examples_index_sqlite": str(sqlite_path),
            "runs_index_results_jsonl": str(results_jsonl),
            "examples_index_build_summary_json": str(summary_json),
        },
        "errors": errors,
    }
    _write_json(summary_json, payload)

    typer.echo(f"examples_index_sqlite {sqlite_path}")
    typer.echo(f"examples_index_build_summary {summary_json}")
    typer.echo(f"indexed_runs {indexed_runs}")
    typer.echo(f"indexed_examples_total {indexed_examples_total}")

    if strict and errors:
        raise typer.Exit(code=1)
