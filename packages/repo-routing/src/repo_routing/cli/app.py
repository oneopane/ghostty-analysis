import typer
from rich import print

from ..config import RepoRoutingConfig
from ..paths import repo_db_path


app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)


@app.command()
def info(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    data_dir: str = typer.Option("data", help="Base directory for per-repo data"),
):
    """Show resolved paths for a repository."""
    cfg = RepoRoutingConfig(repo=repo, data_dir=data_dir)
    print(f"[bold]repo[/bold] {cfg.repo}")
    print(
        f"[bold]db[/bold] {repo_db_path(repo_full_name=cfg.repo, data_dir=cfg.data_dir)}"
    )
