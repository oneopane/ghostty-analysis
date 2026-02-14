from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
from evaluation_harness.db import RepoDb
from repo_routing.api import DEFAULT_PINNED_ARTIFACT_PATHS, HistoryReader

from .pinned_artifacts_plan import build_pinned_artifacts_plan
from .workflow_helpers import (
    CODEOWNERS_PATH_CANDIDATES,
    _iso_utc,
    _parse_dt_option,
    _read_json,
    _resolve_pr_cutoffs,
    _sample_prs,
    _validate_hashed_payload,
    _write_json,
    pinned_artifact_path,
)


def _stable_hash(obj: object) -> str:
    data = json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _doctor_default_output(*, repo: str, data_dir: str, doctor_id: str) -> Path:
    owner, name = repo.split("/", 1)
    return (
        Path(data_dir)
        / "github"
        / owner
        / name
        / "doctor"
        / doctor_id
        / "doctor_summary.json"
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
    output: str | None = typer.Option(
        None,
        help="Optional doctor summary JSON path (default: data/github/<repo>/doctor/<id>/doctor_summary.json)",
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
        db = RepoDb(repo=repo, data_dir=data_dir)
        repo_id = db.repo_id(conn)
        db_max_event = db.max_event_occurred_at(conn)
        db_max_watermark = db.max_watermark_updated_at(conn)
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
            try:
                approval_row = conn.execute(
                    "select count(*) as n from reviews where repo_id = ? and upper(state) = 'APPROVED'",
                    (repo_id,),
                ).fetchone()
            except sqlite3.OperationalError:
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
            try:
                merger_row = conn.execute(
                    """
                    select count(*) as n
                    from events
                    where repo_id = ?
                      and event_type = 'pull_request.merged'
                      and actor_id is not null
                    """,
                    (repo_id,),
                ).fetchone()
            except sqlite3.OperationalError:
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
    pr_base_shas: dict[str, str | None] = {}
    with HistoryReader(repo_full_name=repo, data_dir=data_dir) as reader:
        for n in selected_prs:
            snap = reader.pull_request_snapshot(number=n, as_of=cutoffs[n])
            base_sha = snap.base_sha
            pr_base_shas[str(n)] = base_sha
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

    issues = 0
    if stale_prs:
        issues += 1
    if codeowners_missing:
        issues += 1
    if not approval_ready:
        issues += 1

    generated_at = datetime.now(timezone.utc)
    pr_cutoffs_payload = {str(n): _iso_utc(cutoffs[n]) for n in sorted(cutoffs)}
    doctor_id = _stable_hash(
        {
            "repo": repo,
            "cutoff_policy": cutoff_policy,
            "selected_prs": list(selected_prs),
            "pr_cutoffs": pr_cutoffs_payload,
            "db_max_event_occurred_at": None
            if db_max_event is None
            else _iso_utc(db_max_event),
            "db_max_watermark_updated_at": None
            if db_max_watermark is None
            else _iso_utc(db_max_watermark),
            "cohort_hash": None
            if cohort_payload is None
            else (str(cohort_payload.get("hash") or "") or None),
        }
    )

    out_path = (
        Path(output)
        if output is not None
        else _doctor_default_output(repo=repo, data_dir=data_dir, doctor_id=doctor_id)
    )

    pinned_plan_path = out_path.parent / "pinned_artifacts_plan.json"
    pinned_plan_payload = build_pinned_artifacts_plan(
        repo=repo,
        data_dir=str(data_dir),
        pr_base_shas=pr_base_shas,
        artifact_paths=list(DEFAULT_PINNED_ARTIFACT_PATHS),
        cohort_hash=None
        if cohort_payload is None
        else (str(cohort_payload.get("hash") or "") or None),
        cohort_path=None if cohort is None else str(Path(cohort)),
        doctor_id=doctor_id,
    )
    _write_json(pinned_plan_path, pinned_plan_payload)

    payload: dict[str, Any] = {
        "schema_version": 1,
        "kind": "doctor_summary",
        "doctor_id": doctor_id,
        "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
        "repo": repo,
        "data_dir": str(data_dir),
        "db_path": str(db_path),
        "db_max_event_occurred_at": None
        if db_max_event is None
        else _iso_utc(db_max_event),
        "db_max_watermark_updated_at": None
        if db_max_watermark is None
        else _iso_utc(db_max_watermark),
        "selection": {
            "cohort_path": None if cohort is None else str(Path(cohort)),
            "cohort_hash": None
            if cohort_payload is None
            else (str(cohort_payload.get("hash") or "") or None),
            "filters": {
                "start_at": start_at,
                "end_at": end_at,
                "limit": limit,
                "cutoff_policy": cutoff_policy,
            },
            "pr_numbers": list(selected_prs),
            "pr_cutoffs": pr_cutoffs_payload,
            "pr_base_shas": {
                k: pr_base_shas[k] for k in sorted(pr_base_shas.keys(), key=int)
            },
        },
        "checks": {
            "issues": issues,
            "strict": bool(strict),
            "stale_cutoff": {
                "pass": not bool(stale_prs),
                "stale_prs": list(stale_prs),
            },
            "codeowners": {
                "present": int(codeowners_present),
                "missing": int(len(codeowners_missing)),
                "missing_prs": list(codeowners_missing),
                "pass": not bool(codeowners_missing),
            },
            "profile": {
                "missing_base_sha": int(len(profile_missing_base_sha)),
                "missing_base_sha_prs": list(profile_missing_base_sha),
            },
            "truth": {
                "approval_ready": bool(approval_ready),
                "approval_review_count": int(approval_count),
            },
            "merge": {
                "merger_ready": bool(merger_ready),
                "merger_actor_count": int(merger_actor_count),
            },
            "ingestion_gaps": [
                {"resource": str(r["resource"]), "n": int(r["n"])} for r in gap_rows
            ]
            if gap_rows
            else [],
            "qa_summary": qa_summary,
        },
        "artifacts": {
            "doctor_summary_json": str(out_path),
            "pinned_artifacts_plan_json": str(pinned_plan_path),
        },
    }
    _write_json(out_path, payload)

    typer.echo(f"repo {repo}")
    typer.echo(f"pr_count {len(selected_prs)}")
    typer.echo(f"db_path {db_path}")
    typer.echo(
        f"db_max_event_occurred_at {None if db_max_event is None else _iso_utc(db_max_event)}"
    )
    typer.echo(
        f"db_max_watermark_updated_at {None if db_max_watermark is None else _iso_utc(db_max_watermark)}"
    )
    typer.echo(f"stale_cutoff_prs {len(stale_prs)}")
    if stale_prs:
        typer.echo("stale_cutoff_pr_list " + ",".join(str(n) for n in stale_prs))
    typer.echo(f"codeowners_present {codeowners_present}")
    typer.echo(f"codeowners_missing {len(codeowners_missing)}")
    if codeowners_missing:
        typer.echo(
            "codeowners_missing_prs " + ",".join(str(n) for n in codeowners_missing)
        )
    typer.echo(f"profile_missing_base_sha {len(profile_missing_base_sha)}")
    if gap_rows:
        typer.echo(
            "ingestion_gaps "
            + ", ".join(f"{str(r['resource'])}:{int(r['n'])}" for r in gap_rows)
        )
    else:
        typer.echo("ingestion_gaps none")
    if qa_summary is not None:
        typer.echo("qa_total_gaps " + str(qa_summary.get("total_gaps")))
    typer.echo(f"approval_ready {approval_ready}")
    typer.echo(f"approval_review_count {approval_count}")
    typer.echo(f"merger_ready {merger_ready}")
    typer.echo(f"merger_actor_count {merger_actor_count}")

    typer.echo(f"doctor_summary {out_path}")
    typer.echo(f"pinned_artifacts_plan {pinned_plan_path}")
    if strict and issues > 0:
        raise typer.Exit(code=1)
