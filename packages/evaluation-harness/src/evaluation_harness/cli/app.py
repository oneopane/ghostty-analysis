from __future__ import annotations

from datetime import datetime

import typer
from rich import print

from ..cutoff import cutoff_for_pr
from ..paths import repo_db_path, repo_eval_run_dir
from ..sampling import sample_pr_numbers_created_in_window


app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)


@app.command()
def info(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    data_dir: str = typer.Option("data", help="Base directory for per-repo data"),
):
    """Show resolved paths for a repository."""
    print(f"[bold]repo[/bold] {repo}")
    print(f"[bold]db[/bold] {repo_db_path(repo_full_name=repo, data_dir=data_dir)}")


def _parse_dt(value: str) -> datetime:
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


@app.command("sample")
def sample(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    data_dir: str = typer.Option("data", help="Base directory for per-repo data"),
    start_at: str | None = typer.Option(
        None, "--from", "--start-at", help="ISO created_at window start"
    ),
    end_at: str | None = typer.Option(None, help="ISO created_at window end"),
    limit: int | None = typer.Option(None, help="Max PRs"),
):
    prs = sample_pr_numbers_created_in_window(
        repo=repo,
        data_dir=data_dir,
        start_at=_parse_dt(start_at) if start_at else None,
        end_at=_parse_dt(end_at) if end_at else None,
        limit=limit,
    )
    print(f"[bold]n[/bold] {len(prs)}")
    for n in prs:
        print(n)


@app.command("cutoff")
def cutoff(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    pr_number: int = typer.Option(..., help="Pull request number"),
    data_dir: str = typer.Option("data", help="Base directory for per-repo data"),
):
    c = cutoff_for_pr(repo=repo, pr_number=pr_number, data_dir=data_dir)
    print(c.isoformat())


@app.command("paths")
def paths(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    run_id: str = typer.Option(..., help="Evaluation run id"),
    data_dir: str = typer.Option("data", help="Base directory for per-repo data"),
):
    print(
        f"[bold]eval_run[/bold] {repo_eval_run_dir(repo_full_name=repo, data_dir=data_dir, run_id=run_id)}"
    )
