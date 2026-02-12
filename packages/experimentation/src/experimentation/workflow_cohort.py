from __future__ import annotations

from pathlib import Path

import typer

from .workflow_helpers import (
    _build_cohort_payload,
    _parse_dt_option,
    _write_json,
)


def cohort_create(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    output: str = typer.Option("cohort.json", help="Output cohort JSON path"),
    data_dir: str = typer.Option("data", help="Base directory for repo data"),
    pr: list[int] = typer.Option([], "--pr", help="Explicit PR number(s)"),
    start_at: str | None = typer.Option(
        None, "--from", "--start-at", help="ISO created_at window start"
    ),
    end_at: str | None = typer.Option(None, help="ISO created_at window end"),
    limit: int | None = typer.Option(None, help="Maximum PR count"),
    seed: int | None = typer.Option(None, help="Seed used when sampling with --limit"),
    cutoff_policy: str = typer.Option("created_at", help="Cutoff policy"),
):
    payload = _build_cohort_payload(
        repo=repo,
        data_dir=data_dir,
        pr_numbers=list(pr),
        start_at=_parse_dt_option(start_at, option="--start-at"),
        end_at=_parse_dt_option(end_at, option="--end-at"),
        limit=limit,
        seed=seed,
        cutoff_policy=cutoff_policy,
    )
    out = Path(output)
    _write_json(out, payload)
    typer.echo(f"wrote {out}")
    typer.echo(f"cohort_hash {payload['hash']}")
    typer.echo(f"pr_count {len(payload['pr_numbers'])}")
