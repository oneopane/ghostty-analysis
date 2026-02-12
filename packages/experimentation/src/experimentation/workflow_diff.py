from __future__ import annotations

import typer
from evaluation_harness.paths import repo_eval_run_dir

from .workflow_reports import (
    _delta,
    _load_per_pr_rows,
    _load_report,
    _load_run_context,
)


def experiment_diff(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    run_a: str = typer.Option(..., "--run-a", help="Left run id"),
    run_b: str = typer.Option(..., "--run-b", help="Right run id"),
    data_dir: str = typer.Option("data", help="Base directory for repo data"),
    force: bool = typer.Option(
        False,
        "--force",
        help="Allow comparing runs with missing or mismatched cohort hashes",
    ),
):
    run_a_dir = repo_eval_run_dir(repo_full_name=repo, data_dir=data_dir, run_id=run_a)
    run_b_dir = repo_eval_run_dir(repo_full_name=repo, data_dir=data_dir, run_id=run_b)
    a_context = _load_run_context(run_a_dir)
    b_context = _load_run_context(run_b_dir)
    a_hash = a_context.get("cohort_hash")
    b_hash = b_context.get("cohort_hash")

    if not force:
        if not isinstance(a_hash, str) or not isinstance(b_hash, str):
            raise typer.BadParameter(
                "missing cohort hash in one or both runs; re-run with --force"
            )
        if a_hash != b_hash:
            raise typer.BadParameter(
                f"cohort hash mismatch: {a_hash} != {b_hash}. Use --force to override."
            )

    report_a = _load_report(repo=repo, run_id=run_a, data_dir=data_dir)
    report_b = _load_report(repo=repo, run_id=run_b, data_dir=data_dir)
    rows_a = _load_per_pr_rows(repo=repo, run_id=run_a, data_dir=data_dir)
    rows_b = _load_per_pr_rows(repo=repo, run_id=run_b, data_dir=data_dir)
    prs_a = {int(r.get("pr_number")) for r in rows_a if isinstance(r.get("pr_number"), int)}
    prs_b = {int(r.get("pr_number")) for r in rows_b if isinstance(r.get("pr_number"), int)}
    shared_prs = sorted(prs_a & prs_b)

    typer.echo(f"repo {repo}")
    typer.echo(f"run_a {run_a}")
    typer.echo(f"run_b {run_b}")
    typer.echo(f"cohort_hash_a {a_hash}")
    typer.echo(f"cohort_hash_b {b_hash}")
    typer.echo(f"shared_prs {len(shared_prs)}")

    routing_a = report_a.get("routing_agreement")
    routing_b = report_b.get("routing_agreement")
    if not isinstance(routing_a, dict) or not isinstance(routing_b, dict):
        raise typer.BadParameter("missing routing_agreement in one or both reports")
    common = sorted(set(routing_a.keys()) & set(routing_b.keys()), key=str.lower)
    if not common:
        typer.echo("no overlapping routers")
        raise typer.Exit(code=0)

    for rid in common:
        ra = routing_a.get(rid) or {}
        rb = routing_b.get(rid) or {}
        typer.echo(f"router {rid}")
        typer.echo(f"  hit_at_1 {ra.get('hit_at_1')} -> {rb.get('hit_at_1')} ({_delta(ra.get('hit_at_1'), rb.get('hit_at_1'))})")
        typer.echo(f"  hit_at_3 {ra.get('hit_at_3')} -> {rb.get('hit_at_3')} ({_delta(ra.get('hit_at_3'), rb.get('hit_at_3'))})")
        typer.echo(f"  hit_at_5 {ra.get('hit_at_5')} -> {rb.get('hit_at_5')} ({_delta(ra.get('hit_at_5'), rb.get('hit_at_5'))})")
        typer.echo(f"  mrr {ra.get('mrr')} -> {rb.get('mrr')} ({_delta(ra.get('mrr'), rb.get('mrr'))})")
