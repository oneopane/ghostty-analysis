import asyncio

import typer
from rich import print

from ..ingest.backfill import backfill_repo

app = typer.Typer(add_completion=False)


@app.command()
def ingest(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    db: str = typer.Option(..., help="SQLite database path"),
):
    """Run a one-shot full backfill for a GitHub repository."""
    print(f"[bold]Ingesting[/bold] {repo} -> {db}")
    asyncio.run(backfill_repo(repo, db))
