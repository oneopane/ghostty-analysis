import asyncio
from pathlib import Path

import typer
from rich import print

from ..explorer.server import create_app
from ..ingest.backfill import backfill_repo
from ..ingest.incremental import incremental_update
from ..ingest.pull_requests import backfill_pull_requests
from .paths import default_db_path

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)


@app.command()
def ingest(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    db: str | None = typer.Option(None, help="SQLite database path"),
    data_dir: str = typer.Option(
        "data",
        help="Base directory for per-repo SQLite databases",
    ),
    max_pages: int | None = typer.Option(
        None, help="Dev-only: limit pages per endpoint"
    ),
    start_at: str | None = typer.Option(
        None, "--from", "--start-at", help="ISO timestamp to start at (inclusive)"
    ),
    end_at: str | None = typer.Option(None, help="ISO timestamp to end at (inclusive)"),
):
    """Run a one-shot full backfill for a GitHub repository."""
    db_path = (
        Path(db) if db else default_db_path(repo_full_name=repo, data_dir=data_dir)
    )
    db_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[bold]Ingesting[/bold] {repo} -> {db_path}")
    asyncio.run(
        backfill_repo(
            repo,
            db_path,
            max_pages=max_pages,
            start_at=start_at,
            end_at=end_at,
        )
    )


@app.command()
def incremental(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    db: str | None = typer.Option(None, help="SQLite database path"),
    data_dir: str = typer.Option(
        "data",
        help="Base directory for per-repo SQLite databases",
    ),
):
    """Run an incremental update using stored watermarks."""
    db_path = (
        Path(db) if db else default_db_path(repo_full_name=repo, data_dir=data_dir)
    )
    db_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[bold]Incremental update[/bold] {repo} -> {db_path}")
    asyncio.run(incremental_update(repo, db_path))


@app.command()
def pull_requests(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    db: str | None = typer.Option(None, help="SQLite database path"),
    data_dir: str = typer.Option(
        "data",
        help="Base directory for per-repo SQLite databases",
    ),
    with_truth: bool = typer.Option(
        False,
        help="Also fetch reviews/comments/issue-events for PRs in the window",
    ),
    start_at: str | None = typer.Option(
        None, "--from", "--start-at", help="ISO timestamp to start at (inclusive)"
    ),
    end_at: str | None = typer.Option(None, help="ISO timestamp to end at (inclusive)"),
    max_pages: int | None = typer.Option(
        None, help="Dev-only: limit pages per endpoint"
    ),
):
    """Backfill pull requests created in a time window."""
    db_path = (
        Path(db) if db else default_db_path(repo_full_name=repo, data_dir=data_dir)
    )
    db_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[bold]Pull request backfill[/bold] {repo} -> {db_path}")
    asyncio.run(
        backfill_pull_requests(
            repo,
            db_path,
            with_truth=with_truth,
            start_at=start_at,
            end_at=end_at,
            max_pages=max_pages,
        )
    )


@app.command()
def explore(
    data_root: str = typer.Option(
        "data/github",
        help="Root directory to scan for SQLite files",
    ),
    host: str = typer.Option("127.0.0.1", help="Host interface to bind"),
    port: int = typer.Option(8787, help="Port to bind"),
):
    """Start a local read-only SQLite explorer web app."""
    app_server = create_app(data_root=data_root)
    print(f"[bold]SQLite explorer[/bold] scanning {Path(data_root).resolve()}")
    print(f"Open [cyan]http://{host}:{port}[/cyan] in your browser")
    app_server.run(host=host, port=port, debug=False)
