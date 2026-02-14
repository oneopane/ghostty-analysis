from __future__ import annotations

import typer
from evaluation_harness.api import explain as eval_explain
from evaluation_harness.api import list_runs as eval_list_runs
from evaluation_harness.api import show as eval_show


def experiment_show(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    run_id: str = typer.Option(..., help="Evaluation run id"),
    data_dir: str = typer.Option("data", help="Base directory for repo data"),
):
    try:
        payload = eval_show(repo=repo, run_id=run_id, data_dir=data_dir)
    except FileNotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(payload)


def experiment_list(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    data_dir: str = typer.Option("data", help="Base directory for repo data"),
):
    try:
        runs = eval_list_runs(repo=repo, data_dir=data_dir)
    except FileNotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"n {len(runs)}")
    for run in runs:
        typer.echo(run)


def experiment_explain(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    run_id: str = typer.Option(..., help="Evaluation run id"),
    pr_number: int = typer.Option(..., "--pr", help="Pull request number"),
    router: str | None = typer.Option(None, help="Router id"),
    policy: str | None = typer.Option(None, "--policy", help="Truth policy id"),
    data_dir: str = typer.Option("data", help="Base directory for repo data"),
):
    try:
        payload = eval_explain(
            repo=repo,
            run_id=run_id,
            pr_number=pr_number,
            router=router,
            policy=policy,
            data_dir=data_dir,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(payload)
