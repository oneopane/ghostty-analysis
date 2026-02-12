from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer
from rich import print

from ..artifacts.writer import (
    ArtifactWriter,
    build_pr_snapshot_artifact,
    build_route_artifact,
    iter_pr_numbers_created_in_window,
    pr_created_at,
)
from ..boundary.models import MembershipMode
from ..boundary.pipeline import write_boundary_model_artifacts
from ..config import RepoRoutingConfig
from ..paths import repo_codeowners_dir, repo_db_path
from ..time import cutoff_key_utc, parse_dt_utc


app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)
boundary_app = typer.Typer(help="Boundary model inference commands")
app.add_typer(boundary_app, name="boundary")

_VALID_BASELINES = {
    "mentions",
    "popularity",
    "codeowners",
    "union",
    "hybrid_ranker",
    "llm_rerank",
    "stewards",
}


def _parse_iso_utc(value: str, *, param: str) -> datetime:
    try:
        dt = parse_dt_utc(value)
    except ValueError as exc:
        raise typer.BadParameter(f"invalid ISO timestamp for {param}: {value}") from exc
    if dt is None:
        raise typer.BadParameter(f"missing {param}")
    return dt


def _normalize_baselines(values: list[str]) -> list[str]:
    normalized = [v.strip().lower() for v in values if v.strip()]
    if not normalized:
        raise typer.BadParameter("at least one baseline is required")

    unknown = sorted({b for b in normalized if b not in _VALID_BASELINES})
    if unknown:
        valid = ", ".join(sorted(_VALID_BASELINES))
        raise typer.BadParameter(
            f"unknown baseline(s): {', '.join(unknown)}. valid: {valid}"
        )
    return normalized


def _validate_stewards_config(*, baselines: list[str], config: str | None) -> str | None:
    if "stewards" not in baselines:
        return config
    if config is None:
        raise typer.BadParameter("--config is required when baseline includes stewards")
    config_path = Path(config)
    if not config_path.exists():
        raise typer.BadParameter(f"--config path does not exist: {config_path}")
    return str(config_path)


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
    as_of_dt = _parse_iso_utc(as_of, param="--as-of")
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
        ...,
        help="Baseline: mentions | popularity | codeowners | union | hybrid_ranker | llm_rerank | stewards",
    ),
    config: str | None = typer.Option(
        None, help="Scoring config path (required for stewards)"
    ),
    run_id: str = typer.Option(..., help="Evaluation run id"),
    as_of: str = typer.Option(..., help="ISO timestamp cutoff"),
    top_k: int = typer.Option(5, help="Number of candidates to emit"),
    data_dir: str = typer.Option("data", help="Base directory for per-repo data"),
):
    """Run one baseline and emit a RouteResult artifact."""
    cfg = RepoRoutingConfig(repo=repo, data_dir=data_dir)
    baselines = _normalize_baselines([baseline])
    config_path = _validate_stewards_config(baselines=baselines, config=config)
    as_of_dt = _parse_iso_utc(as_of, param="--as-of")

    artifact = build_route_artifact(
        baseline=baselines[0],
        repo=cfg.repo,
        pr_number=pr_number,
        as_of=as_of_dt,
        data_dir=cfg.data_dir,
        top_k=top_k,
        config_path=config_path,
    )
    writer = ArtifactWriter(repo=cfg.repo, data_dir=cfg.data_dir, run_id=run_id)
    out = writer.write_route_result(artifact)
    print(f"[bold]wrote[/bold] {out}")


@boundary_app.command("build")
def boundary_build(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    as_of: str = typer.Option(..., help="ISO timestamp cutoff"),
    data_dir: str = typer.Option("data", help="Base directory for per-repo data"),
    strategy: str = typer.Option(
        "hybrid_path_cochange.v1", help="Boundary strategy id"
    ),
    membership_mode: str = typer.Option(
        "mixed", help="Membership mode: hard | overlap | mixed"
    ),
    path_weight: float = typer.Option(1.0, help="Path prior weight"),
    cochange_weight: float = typer.Option(0.35, help="Co-change signal weight"),
    parser_enabled: bool = typer.Option(False, help="Enable parser signal channel"),
    parser_backend_id: str = typer.Option("python.ast.v1", help="Parser backend id"),
    parser_snapshot_root: str | None = typer.Option(None, help="Pinned source snapshot root"),
    parser_weight: float = typer.Option(0.2, help="Parser signal channel weight"),
    parser_strict: bool = typer.Option(False, help="Fail if parser snapshot is unavailable"),
):
    """Build deterministic boundary model artifacts for a repo/cutoff."""
    cfg = RepoRoutingConfig(repo=repo, data_dir=data_dir)
    cutoff = _parse_iso_utc(as_of, param="--as-of")

    try:
        mode = MembershipMode(membership_mode.lower())
    except ValueError as exc:
        raise typer.BadParameter(
            "--membership-mode must be one of: hard, overlap, mixed"
        ) from exc

    artifact = write_boundary_model_artifacts(
        repo_full_name=cfg.repo,
        cutoff_utc=cutoff,
        cutoff_key=cutoff_key_utc(cutoff),
        strategy_id=strategy,
        data_dir=cfg.data_dir,
        membership_mode=mode,
        strategy_config={
            "path_weight": path_weight,
            "cochange_weight": cochange_weight,
            "parser_enabled": parser_enabled,
            "parser_backend_id": parser_backend_id,
            "parser_snapshot_root": parser_snapshot_root,
            "parser_weight": parser_weight,
            "parser_strict": parser_strict,
        },
    )

    print(
        "[bold]wrote[/bold] "
        f"strategy={artifact.manifest.strategy_id} "
        f"hash={artifact.manifest.model_hash} "
        f"units={artifact.manifest.unit_count} "
        f"boundaries={artifact.manifest.boundary_count}"
    )


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
    config: str | None = typer.Option(
        None, help="Scoring config path (used by stewards)"
    ),
    data_dir: str = typer.Option("data", help="Base directory for per-repo data"),
):
    """Build snapshot + baseline routing artifacts for a PR list/window."""
    cfg = RepoRoutingConfig(repo=repo, data_dir=data_dir)
    baselines = _normalize_baselines(list(baseline))
    config_path = _validate_stewards_config(baselines=baselines, config=config)

    as_of_dt: datetime | None = (
        _parse_iso_utc(as_of, param="--as-of") if as_of is not None else None
    )
    start_dt = _parse_iso_utc(start_at, param="--start-at") if start_at else None
    end_dt = _parse_iso_utc(end_at, param="--end-at") if end_at else None

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

    if not pr_numbers:
        raise typer.BadParameter("no PRs selected")

    # Preflight PR cutoffs before any artifact writes.
    cutoff_by_pr: dict[int, datetime] = {}
    for pr_number in pr_numbers:
        if as_of_dt is not None:
            cutoff_by_pr[pr_number] = as_of_dt
            continue

        created = pr_created_at(repo=cfg.repo, data_dir=cfg.data_dir, pr_number=pr_number)
        if created is None:
            raise typer.BadParameter(f"missing created_at for {cfg.repo}#{pr_number}")
        cutoff_by_pr[pr_number] = created

    writer = ArtifactWriter(repo=cfg.repo, data_dir=cfg.data_dir, run_id=run_id)
    for pr_number in pr_numbers:
        cutoff = cutoff_by_pr[pr_number]

        # Build first, write second: no partial per-PR outputs if route build fails.
        snap = build_pr_snapshot_artifact(
            repo=cfg.repo,
            pr_number=pr_number,
            as_of=cutoff,
            data_dir=cfg.data_dir,
        )
        route_artifacts = [
            build_route_artifact(
                baseline=b,
                repo=cfg.repo,
                pr_number=pr_number,
                as_of=cutoff,
                data_dir=cfg.data_dir,
                top_k=top_k,
                config_path=config_path,
            )
            for b in baselines
        ]

        snap_path = writer.write_pr_snapshot(snap)
        print(f"[bold]wrote[/bold] {snap_path}")
        for art in route_artifacts:
            route_path = writer.write_route_result(art)
            print(f"[bold]wrote[/bold] {route_path}")
