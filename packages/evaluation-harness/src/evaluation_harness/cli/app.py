from __future__ import annotations

from datetime import datetime

import typer
from rich import print

from ..cutoff import cutoff_for_pr
from ..paths import (
    eval_per_pr_jsonl_path,
    eval_report_json_path,
    eval_report_md_path,
    repo_db_path,
    repo_eval_dir,
    repo_eval_run_dir,
)
from ..config import EvalRunConfig
from ..sampling import sample_pr_numbers_created_in_window
from ..run_id import compute_run_id
from ..runner import run_streaming_eval


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


@app.command("list")
def list_runs(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    data_dir: str = typer.Option("data", help="Base directory for per-repo data"),
):
    base = repo_eval_dir(repo_full_name=repo, data_dir=data_dir)
    if not base.exists():
        print(f"[bold]eval_dir[/bold] {base}")
        print("(missing)")
        raise typer.Exit(code=1)

    runs = [p.name for p in base.iterdir() if p.is_dir()]
    runs.sort(key=lambda s: s.lower())
    print(f"[bold]n[/bold] {len(runs)}")
    for r in runs:
        print(r)


@app.command("show")
def show(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    run_id: str = typer.Option(..., help="Evaluation run id"),
    data_dir: str = typer.Option("data", help="Base directory for per-repo data"),
):
    p = eval_report_md_path(repo_full_name=repo, data_dir=data_dir, run_id=run_id)
    if p.exists():
        print(p.read_text(encoding="utf-8").rstrip("\n"))
        return

    pj = eval_report_json_path(repo_full_name=repo, data_dir=data_dir, run_id=run_id)
    if pj.exists():
        print(pj.read_text(encoding="utf-8").rstrip("\n"))
        return

    raise typer.BadParameter(f"missing report: {p} / {pj}")


@app.command("explain")
def explain(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    run_id: str = typer.Option(..., help="Evaluation run id"),
    pr_number: int = typer.Option(..., "--pr", help="Pull request number"),
    baseline: str | None = typer.Option(None, help="Baseline (default: first present)"),
    data_dir: str = typer.Option("data", help="Base directory for per-repo data"),
):
    import json

    p = eval_per_pr_jsonl_path(repo_full_name=repo, data_dir=data_dir, run_id=run_id)
    if not p.exists():
        raise typer.BadParameter(f"missing per_pr.jsonl: {p}")

    row: dict | None = None
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if int(obj.get("pr_number", -1)) == pr_number:
            row = obj
            break
    if row is None:
        raise typer.BadParameter(f"pr not found in per_pr.jsonl: {pr_number}")

    baselines = row.get("baselines") or {}
    if not isinstance(baselines, dict) or not baselines:
        raise typer.BadParameter("missing baselines for pr")

    chosen = baseline
    if chosen is None:
        chosen = sorted(baselines.keys(), key=lambda s: str(s).lower())[0]
    if chosen not in baselines:
        raise typer.BadParameter(f"baseline not found: {chosen}")

    print(f"[bold]repo[/bold] {repo}")
    print(f"[bold]run_id[/bold] {run_id}")
    print(f"[bold]pr[/bold] {pr_number}")
    print(f"[bold]cutoff[/bold] {row.get('cutoff')}")
    print(f"[bold]baseline[/bold] {chosen}")
    print("")

    print("[bold]truth_behavior[/bold]")
    for t in row.get("truth_behavior") or []:
        print(f"- {t}")
    print("")

    b = baselines[chosen]
    rr = b.get("route_result") or {}
    print("[bold]candidates[/bold]")
    for c in rr.get("candidates") or []:
        target = (c.get("target") or {}).get("name")
        score = c.get("score")
        print(f"- {target} (score={score})")
        for ev in c.get("evidence") or []:
            kind = ev.get("kind")
            data = ev.get("data")
            print(f"  {kind}: {data}")
    print("")

    print("[bold]routing_agreement[/bold]")
    print(
        json.dumps(
            b.get("routing_agreement") or {},
            sort_keys=True,
            indent=2,
            ensure_ascii=True,
        )
    )
    print("")

    print("[bold]gates[/bold]")
    print(
        json.dumps(row.get("gates") or {}, sort_keys=True, indent=2, ensure_ascii=True)
    )
    print("")

    print("[bold]queue[/bold]")
    print(json.dumps(b.get("queue") or {}, sort_keys=True, indent=2, ensure_ascii=True))


@app.command("run")
def run(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    data_dir: str = typer.Option("data", help="Base directory for per-repo data"),
    run_id: str | None = typer.Option(None, help="Run id (default: computed)"),
    pr_number: list[int] = typer.Option([], "--pr", help="PR number (repeatable)"),
    start_at: str | None = typer.Option(
        None, "--from", "--start-at", help="ISO created_at window start"
    ),
    end_at: str | None = typer.Option(None, help="ISO created_at window end"),
    limit: int | None = typer.Option(None, help="Max PRs"),
    baseline: list[str] = typer.Option(
        ["mentions"], "--baseline", "--router", help="Router(s) to evaluate"
    ),
    config: str | None = typer.Option(
        None, "--config", help="Router config path (required for stewards)"
    ),
):
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

    cfg = EvalRunConfig(repo=repo, data_dir=data_dir, run_id=run_id or "run")
    if run_id is None:
        cfg.run_id = compute_run_id(cfg=cfg)

    res = run_streaming_eval(
        cfg=cfg,
        pr_numbers=list(prs),
        baselines=list(baseline),
        router_config_path=config,
    )
    # Use plain output (no rich wrapping) for machine parsing.
    typer.echo(f"run_dir {res.run_dir}")
