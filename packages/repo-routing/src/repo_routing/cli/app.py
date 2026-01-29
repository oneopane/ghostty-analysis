from __future__ import annotations

from datetime import datetime

import typer
from rich import print

from ..artifacts.writer import (
    ArtifactWriter,
    build_pr_snapshot_artifact,
    build_route_artifact,
    iter_pr_numbers_created_in_window,
    pr_created_at,
)
from ..config import RepoRoutingConfig
from ..paths import repo_codeowners_dir, repo_db_path


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
    print(
        f"[bold]codeowners_dir[/bold] {repo_codeowners_dir(repo_full_name=cfg.repo, data_dir=cfg.data_dir)}"
    )


def _parse_as_of(value: str) -> datetime:
    # Accept either ISO with timezone or naive ISO; stored timestamps are UTC-ish.
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


@app.command()
def snapshot(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    pr_number: int = typer.Option(..., help="Pull request number"),
    run_id: str = typer.Option(..., help="Evaluation run id"),
    as_of: str = typer.Option(..., help="ISO timestamp cutoff"),
    data_dir: str = typer.Option("data", help="Base directory for per-repo data"),
):
    """Build a deterministic PR snapshot artifact."""
    cfg = RepoRoutingConfig(repo=repo, data_dir=data_dir)
    as_of_dt = _parse_as_of(as_of)
    artifact = build_pr_snapshot_artifact(
        repo=cfg.repo, pr_number=pr_number, as_of=as_of_dt, data_dir=cfg.data_dir
    )
    writer = ArtifactWriter(repo=cfg.repo, data_dir=cfg.data_dir, run_id=run_id)
    out = writer.write_pr_snapshot(artifact)
    print(f"[bold]wrote[/bold] {out}")


@app.command()
def route(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    pr_number: int = typer.Option(..., help="Pull request number"),
    baseline: str = typer.Option(
        ..., help="Baseline: mentions | popularity | codeowners"
    ),
    run_id: str = typer.Option(..., help="Evaluation run id"),
    as_of: str = typer.Option(..., help="ISO timestamp cutoff"),
    top_k: int = typer.Option(5, help="Number of candidates to emit"),
    data_dir: str = typer.Option("data", help="Base directory for per-repo data"),
):
    """Run one baseline and emit a RouteResult artifact."""
    cfg = RepoRoutingConfig(repo=repo, data_dir=data_dir)
    as_of_dt = _parse_as_of(as_of)
    artifact = build_route_artifact(
        baseline=baseline,
        repo=cfg.repo,
        pr_number=pr_number,
        as_of=as_of_dt,
        data_dir=cfg.data_dir,
        top_k=top_k,
    )
    writer = ArtifactWriter(repo=cfg.repo, data_dir=cfg.data_dir, run_id=run_id)
    out = writer.write_route_result(artifact)
    print(f"[bold]wrote[/bold] {out}")


@app.command("build-artifacts")
def build_artifacts(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    run_id: str = typer.Option(..., help="Evaluation run id"),
    as_of: str | None = typer.Option(
        None,
        help="ISO timestamp cutoff; defaults per-PR to created_at",
    ),
    top_k: int = typer.Option(5, help="Number of candidates to emit"),
    start_at: str | None = typer.Option(
        None, "--from", "--start-at", help="ISO created_at window start"
    ),
    end_at: str | None = typer.Option(None, help="ISO created_at window end"),
    pr: list[int] = typer.Option(
        [],
        "--pr",
        help="Explicit PR number(s). If provided, window options are ignored.",
    ),
    baseline: list[str] = typer.Option(
        ["mentions", "popularity", "codeowners"],
        help="Baselines to run",
    ),
    data_dir: str = typer.Option("data", help="Base directory for per-repo data"),
):
    """Build snapshot + baseline routing artifacts for a PR list/window."""
    cfg = RepoRoutingConfig(repo=repo, data_dir=data_dir)

    as_of_dt: datetime | None = _parse_as_of(as_of) if as_of is not None else None
    start_dt = _parse_as_of(start_at) if start_at is not None else None
    end_dt = _parse_as_of(end_at) if end_at is not None else None

    pr_numbers: list[int]
    if pr:
        pr_numbers = sorted(set(pr))
    else:
        pr_numbers = list(
            iter_pr_numbers_created_in_window(
                repo=cfg.repo,
                data_dir=cfg.data_dir,
                start_at=start_dt,
                end_at=end_dt,
            )
        )

    writer = ArtifactWriter(repo=cfg.repo, data_dir=cfg.data_dir, run_id=run_id)
    for pr_number in pr_numbers:
        cutoff = as_of_dt
        if cutoff is None:
            created = pr_created_at(
                repo=cfg.repo, data_dir=cfg.data_dir, pr_number=pr_number
            )
            if created is None:
                raise RuntimeError(f"missing created_at for {cfg.repo}#{pr_number}")
            cutoff = created

        snap = build_pr_snapshot_artifact(
            repo=cfg.repo,
            pr_number=pr_number,
            as_of=cutoff,
            data_dir=cfg.data_dir,
        )
        snap_path = writer.write_pr_snapshot(snap)
        print(f"[bold]wrote[/bold] {snap_path}")

        for b in baseline:
            art = build_route_artifact(
                baseline=b,
                repo=cfg.repo,
                pr_number=pr_number,
                as_of=cutoff,
                data_dir=cfg.data_dir,
                top_k=top_k,
            )
            route_path = writer.write_route_result(art)
            print(f"[bold]wrote[/bold] {route_path}")
