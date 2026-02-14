from __future__ import annotations

from pathlib import Path

import typer
from evaluation_harness.api import write_compare_summary, write_run_summary
from evaluation_harness.paths import repo_eval_run_dir
from repo_routing.runtime_defaults import DEFAULT_DATA_DIR

from .examples_index import index_run as index_examples_run


def experiment_summarize(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    run_id: str = typer.Option(..., "--run-id", help="Evaluation run id"),
    data_dir: str = typer.Option(DEFAULT_DATA_DIR, help="Base directory for repo data"),
    index: bool = typer.Option(
        True,
        "--index/--no-index",
        help="Update examples_index.sqlite for this run",
    ),
):
    run_dir = repo_eval_run_dir(repo_full_name=repo, data_dir=data_dir, run_id=run_id)
    if not run_dir.exists():
        raise typer.BadParameter(f"missing run dir: {run_dir}")
    if not (run_dir / "report.json").exists():
        raise typer.BadParameter(f"missing report.json: {run_dir / 'report.json'}")
    if not (run_dir / "manifest.json").exists():
        raise typer.BadParameter(f"missing manifest.json: {run_dir / 'manifest.json'}")

    out = write_run_summary(repo=repo, run_id=run_id, run_dir=run_dir)
    typer.echo(f"run_summary {out}")

    if index:
        sqlite_path, indexed_n = index_examples_run(
            repo=repo,
            run_id=run_id,
            data_dir=data_dir,
            run_dir=run_dir,
        )
        typer.echo(f"examples_index_sqlite {sqlite_path}")
        typer.echo(f"indexed_examples {indexed_n}")


def experiment_compare(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    run_a: str = typer.Option(..., "--run-a", help="Baseline run id"),
    run_b: str = typer.Option(..., "--run-b", help="Candidate run id"),
    data_dir: str = typer.Option(DEFAULT_DATA_DIR, help="Base directory for repo data"),
    output_dir: str | None = typer.Option(
        None,
        help="Optional output directory for compare artifacts (default: repo eval/_compare)",
    ),
):
    out = write_compare_summary(
        repo=repo,
        data_dir=data_dir,
        baseline_run_id=run_a,
        candidate_run_id=run_b,
        out_dir=None if output_dir is None else Path(output_dir),
    )
    typer.echo(f"compare_summary {out}")
