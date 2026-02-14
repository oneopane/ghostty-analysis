from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer
from rich import print
from repo_routing.runtime_defaults import DEFAULT_DATA_DIR
from repo_routing.router_specs import build_router_specs
from repo_routing.time import parse_dt_utc

from ..config import EvalDefaults, EvalRunConfig
from ..cutoff import cutoff_for_pr
from ..paths import repo_db_path, repo_eval_run_dir
from ..run_id import compute_run_id
from ..compare_summary import write_compare_summary
from ..sampling import sample_pr_numbers_created_in_window
from ..service import cutoff_horizon_check
from ..service import explain as explain_eval
from ..service import list_runs as list_eval_runs
from ..service import run as run_eval
from ..service import show as show_eval


app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)


def _parse_dt(value: str) -> datetime:
    try:
        dt = parse_dt_utc(value)
    except ValueError as exc:
        raise typer.BadParameter(f"invalid ISO timestamp: {value}") from exc
    if dt is None:
        raise typer.BadParameter("missing datetime value")
    return dt


@app.command()
def info(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    data_dir: str = typer.Option(
        DEFAULT_DATA_DIR, help="Base directory for per-repo data"
    ),
):
    """Show resolved paths for a repository."""
    print(f"[bold]repo[/bold] {repo}")
    print(f"[bold]db[/bold] {repo_db_path(repo_full_name=repo, data_dir=data_dir)}")


@app.command("sample")
def sample(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    data_dir: str = typer.Option(
        DEFAULT_DATA_DIR, help="Base directory for per-repo data"
    ),
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
    pr_number: int | None = typer.Option(None, help="Pull request number"),
    cutoff: str | None = typer.Option(None, help="ISO cutoff timestamp for horizon check"),
    data_dir: str = typer.Option(
        DEFAULT_DATA_DIR, help="Base directory for per-repo data"
    ),
):
    if cutoff is not None:
        out = cutoff_horizon_check(repo=repo, cutoff=cutoff, data_dir=data_dir)
        typer.echo("pass" if out["ok"] else "fail")
        typer.echo(out)
        if not out["ok"]:
            raise typer.Exit(code=1)
        return

    if pr_number is None:
        raise typer.BadParameter("either --pr-number or --cutoff is required")

    c = cutoff_for_pr(repo=repo, pr_number=pr_number, data_dir=data_dir)
    print(c.isoformat())


@app.command("paths")
def paths(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    run_id: str = typer.Option(..., help="Evaluation run id"),
    data_dir: str = typer.Option(
        DEFAULT_DATA_DIR, help="Base directory for per-repo data"
    ),
):
    print(
        f"[bold]eval_run[/bold] {repo_eval_run_dir(repo_full_name=repo, data_dir=data_dir, run_id=run_id)}"
    )


@app.command("list")
def list_runs(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    data_dir: str = typer.Option(
        DEFAULT_DATA_DIR, help="Base directory for per-repo data"
    ),
):
    try:
        runs = list_eval_runs(repo=repo, data_dir=data_dir)
    except FileNotFoundError as exc:
        print(f"[bold]eval_dir[/bold] {Path(str(exc)).as_posix() if str(exc) else exc}")
        print("(missing)")
        raise typer.Exit(code=1)

    print(f"[bold]n[/bold] {len(runs)}")
    for r in runs:
        print(r)


@app.command("show")
def show(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    run_id: str = typer.Option(..., help="Evaluation run id"),
    data_dir: str = typer.Option(
        DEFAULT_DATA_DIR, help="Base directory for per-repo data"
    ),
):
    try:
        payload = show_eval(repo=repo, run_id=run_id, data_dir=data_dir)
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"missing report: {exc}") from exc
    print(payload)


@app.command("explain")
def explain(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    run_id: str = typer.Option(..., help="Evaluation run id"),
    pr_number: int = typer.Option(..., "--pr", help="Pull request number"),
    router: str | None = typer.Option(None, help="Router id (default: first present)"),
    policy: str | None = typer.Option(None, "--policy", help="Truth policy id"),
    data_dir: str = typer.Option(
        DEFAULT_DATA_DIR, help="Base directory for per-repo data"
    ),
):
    try:
        payload = explain_eval(
            repo=repo,
            run_id=run_id,
            pr_number=pr_number,
            router=router,
            policy=policy,
            data_dir=data_dir,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    print(payload)


@app.command("run")
def run(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    data_dir: str = typer.Option(
        DEFAULT_DATA_DIR, help="Base directory for per-repo data"
    ),
    run_id: str | None = typer.Option(None, help="Run id (default: computed)"),
    pr_number: list[int] = typer.Option([], "--pr", help="PR number (repeatable)"),
    start_at: str | None = typer.Option(
        None, "--from", "--start-at", help="ISO created_at window start"
    ),
    end_at: str | None = typer.Option(None, help="ISO created_at window end"),
    limit: int | None = typer.Option(None, help="Max PRs"),
    router: list[str] = typer.Option(
        [], "--router", help="Builtin router name(s) (repeatable)"
    ),
    router_import: list[str] = typer.Option(
        [], "--router-import", help="Import-path router(s): pkg.mod:ClassOrFactory"
    ),
    router_config: list[str] = typer.Option(
        [],
        "--router-config",
        help="Router config path(s): router_id=path, name=path, or positional",
    ),
    config: str | None = typer.Option(
        None,
        "--config",
        help="Deprecated single router config path (maps to stewards router)",
    ),
    execution_mode: str = typer.Option(
        "sequential",
        help="Execution mode: sequential | parallel",
    ),
    max_workers: int | None = typer.Option(
        None,
        help="Max workers for --execution-mode=parallel",
    ),
):
    configs = list(router_config)
    if config is not None:
        configs.insert(0, f"stewards={config}")

    try:
        specs = build_router_specs(
            routers=list(router),
            router_imports=list(router_import),
            router_configs=configs,
            stewards_config_required_message="--config is required when router includes stewards",
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    prs = pr_number
    if not prs:
        prs = sample_pr_numbers_created_in_window(
            repo=repo,
            data_dir=data_dir,
            start_at=_parse_dt(start_at) if start_at else None,
            end_at=_parse_dt(end_at) if end_at else None,
            limit=limit,
        )
    if not prs:
        raise typer.BadParameter("no PRs selected")

    defaults = EvalDefaults(
        execution_mode=execution_mode,
        max_workers=max_workers,
    )
    cfg = EvalRunConfig(
        repo=repo,
        data_dir=data_dir,
        run_id=run_id or "run",
        defaults=defaults,
    )
    if run_id is None:
        cfg.run_id = compute_run_id(cfg=cfg)

    res = run_eval(
        cfg=cfg,
        pr_numbers=list(prs),
        router_specs=specs,
    )
    typer.echo(f"run_dir {res.run_dir}")


@app.command("compare")
def compare(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    baseline_run_id: str = typer.Option(..., "--baseline", help="Baseline run id"),
    candidate_run_id: str = typer.Option(..., "--candidate", help="Candidate run id"),
    data_dir: str = typer.Option(
        DEFAULT_DATA_DIR, help="Base directory for per-repo data"
    ),
    output_dir: str | None = typer.Option(
        None,
        help="Optional output directory for compare artifacts (default: repo eval/_compare)",
    ),
):
    out = write_compare_summary(
        repo=repo,
        data_dir=data_dir,
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
        out_dir=None if output_dir is None else Path(output_dir),
    )
    typer.echo(f"compare_summary {out}")
