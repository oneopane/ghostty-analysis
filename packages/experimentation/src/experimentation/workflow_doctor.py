from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import typer
from repo_routing.api import HistoryReader, parse_dt_utc

from .workflow_helpers import (
    CODEOWNERS_PATH_CANDIDATES,
    _iso_utc,
    _parse_dt_option,
    _read_json,
    _resolve_pr_cutoffs,
    _sample_prs,
    _validate_hashed_payload,
    pinned_artifact_path,
)


def doctor(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    data_dir: str = typer.Option("data", help="Base directory for repo data"),
    cohort: str | None = typer.Option(None, help="Optional cohort JSON path"),
    pr: list[int] = typer.Option([], "--pr", help="Explicit PR number(s)"),
    start_at: str | None = typer.Option(
        None, "--from", "--start-at", help="ISO created_at window start"
    ),
    end_at: str | None = typer.Option(None, help="ISO created_at window end"),
    limit: int | None = typer.Option(None, help="Maximum PR count"),
    cutoff_policy: str = typer.Option("created_at", help="Cutoff policy"),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Exit non-zero on stale-cutoff or profile-coverage issues",
    ),
):
    cohort_payload: dict[str, Any] | None = None
    selected_prs: list[int]
    if cohort is not None:
        cpath = Path(cohort)
        cohort_payload = _validate_hashed_payload(
            payload=_read_json(cpath),
            kind="cohort",
            path=cpath,
        )
        if str(cohort_payload.get("repo") or "") != repo:
            raise typer.BadParameter("cohort repo mismatch")
        selected_prs = [int(x) for x in cohort_payload.get("pr_numbers") or []]
    else:
        selected_prs = _sample_prs(
            repo=repo,
            data_dir=data_dir,
            pr_numbers=list(pr),
            start_at=_parse_dt_option(start_at, option="--start-at"),
            end_at=_parse_dt_option(end_at, option="--end-at"),
            limit=limit,
            seed=None,
        )

    if not selected_prs:
        raise typer.BadParameter("no PRs selected")

    cutoffs = _resolve_pr_cutoffs(
        repo=repo,
        data_dir=data_dir,
        pr_numbers=selected_prs,
        cutoff_policy=cutoff_policy,
        cohort_payload=cohort_payload,
        require_complete_from_cohort=False,
    )

    owner, name = repo.split("/", 1)
    db_path = Path(data_dir) / "github" / owner / name / "history.sqlite"
    if not db_path.exists():
        raise typer.BadParameter(f"missing DB: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("select max(occurred_at) as max_at from events").fetchone()
        db_max_event = None if row is None else parse_dt_utc(row["max_at"])
        try:
            gap_rows = conn.execute(
                """
                select resource, count(*) as n
                from ingestion_gaps
                group by resource
                order by resource asc
                """
            ).fetchall()
        except sqlite3.OperationalError:
            gap_rows = []
        try:
            qa_row = conn.execute(
                "select summary_json from qa_reports order by id desc limit 1"
            ).fetchone()
        except sqlite3.OperationalError:
            qa_row = None

        approval_count = 0
        approval_ready = False
        try:
            approval_row = conn.execute(
                "select count(*) as n from reviews where upper(state) = 'APPROVED'"
            ).fetchone()
            approval_count = int(approval_row["n"]) if approval_row is not None else 0
            approval_ready = approval_count > 0
        except sqlite3.OperationalError:
            approval_count = 0
            approval_ready = False

        merger_actor_count = 0
        merger_ready = False
        try:
            merger_row = conn.execute(
                """
                select count(*) as n
                from events
                where event_type = 'pull_request.merged'
                  and actor_id is not null
                """
            ).fetchone()
            merger_actor_count = int(merger_row["n"]) if merger_row is not None else 0
            merger_ready = merger_actor_count > 0
        except sqlite3.OperationalError:
            merger_actor_count = 0
            merger_ready = False
    finally:
        conn.close()

    stale_prs: list[int] = []
    if db_max_event is not None:
        stale_prs = [n for n in selected_prs if cutoffs[n] > db_max_event]

    codeowners_present = 0
    codeowners_missing: list[int] = []
    profile_missing_base_sha: list[int] = []
    with HistoryReader(repo_full_name=repo, data_dir=data_dir) as reader:
        for n in selected_prs:
            snap = reader.pull_request_snapshot(number=n, as_of=cutoffs[n])
            base_sha = snap.base_sha
            if not base_sha:
                profile_missing_base_sha.append(n)
                codeowners_missing.append(n)
                continue
            found = False
            for rel in CODEOWNERS_PATH_CANDIDATES:
                p = pinned_artifact_path(
                    repo_full_name=repo,
                    base_sha=base_sha,
                    relative_path=rel,
                    data_dir=data_dir,
                )
                if p.exists():
                    found = True
                    break
            if found:
                codeowners_present += 1
            else:
                codeowners_missing.append(n)

    qa_summary = None
    if qa_row is not None and qa_row["summary_json"]:
        try:
            qa_summary = json.loads(str(qa_row["summary_json"]))
        except Exception:
            qa_summary = None

    typer.echo(f"repo {repo}")
    typer.echo(f"pr_count {len(selected_prs)}")
    typer.echo(f"db_path {db_path}")
    typer.echo(f"db_max_event_occurred_at {None if db_max_event is None else _iso_utc(db_max_event)}")
    typer.echo(f"stale_cutoff_prs {len(stale_prs)}")
    if stale_prs:
        typer.echo("stale_cutoff_pr_list " + ",".join(str(n) for n in stale_prs))
    typer.echo(f"codeowners_present {codeowners_present}")
    typer.echo(f"codeowners_missing {len(codeowners_missing)}")
    if codeowners_missing:
        typer.echo("codeowners_missing_prs " + ",".join(str(n) for n in codeowners_missing))
    typer.echo(f"profile_missing_base_sha {len(profile_missing_base_sha)}")
    if gap_rows:
        typer.echo(
            "ingestion_gaps "
            + ", ".join(f"{str(r['resource'])}:{int(r['n'])}" for r in gap_rows)
        )
    else:
        typer.echo("ingestion_gaps none")
    if qa_summary is not None:
        typer.echo(
            "qa_total_gaps " + str(qa_summary.get("total_gaps"))
        )
    typer.echo(f"approval_ready {approval_ready}")
    typer.echo(f"approval_review_count {approval_count}")
    typer.echo(f"merger_ready {merger_ready}")
    typer.echo(f"merger_actor_count {merger_actor_count}")

    issues = 0
    if stale_prs:
        issues += 1
    if codeowners_missing:
        issues += 1
    if not approval_ready:
        issues += 1
    if strict and issues > 0:
        raise typer.Exit(code=1)
