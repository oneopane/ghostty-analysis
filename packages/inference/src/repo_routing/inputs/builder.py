from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from ..boundary.consumption import project_files_to_boundary_footprint
from ..boundary.io import read_boundary_artifact
from ..history.reader import HistoryReader
from ..paths import repo_db_path
from ..parsing.gates import parse_gate_fields
from ..time import cutoff_key_utc, dt_sql_utc, require_dt_utc
from .models import (
    PRGateFields,
    PRInputBuilderOptions,
    PRInputBundle,
    RecentActivityEvent,
)


def _recent_activity_window(
    *,
    repo: str,
    data_dir: str | Path,
    cutoff: datetime,
    options: PRInputBuilderOptions,
) -> list[RecentActivityEvent]:
    if options.recent_activity_limit <= 0:
        return []

    db_path = repo_db_path(repo_full_name=repo, data_dir=data_dir)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "select id from repos where full_name = ?",
            (repo,),
        ).fetchone()
        if row is None:
            raise KeyError(f"repo not found in db: {repo}")
        repo_id = int(row["id"])

        start = cutoff - options.recent_activity_window
        start_s = dt_sql_utc(start, timespec="microseconds")
        cutoff_s = dt_sql_utc(cutoff, timespec="microseconds")

        limit = int(options.recent_activity_limit)
        rows = conn.execute(
            """
            select kind, actor_login, occurred_at
            from (
              select
                'review' as kind,
                u.login as actor_login,
                r.submitted_at as occurred_at
              from reviews r
              join users u on u.id = r.user_id
              where r.repo_id = ?
                and r.submitted_at is not null
                and r.submitted_at >= ?
                and r.submitted_at <= ?
                and u.login is not null
                and (u.type is null or u.type != 'Bot')

              union all

              select
                'comment' as kind,
                u.login as actor_login,
                c.created_at as occurred_at
              from comments c
              join users u on u.id = c.user_id
              where c.repo_id = ?
                and c.pull_request_id is not null
                and c.created_at is not null
                and c.created_at >= ?
                and c.created_at <= ?
                and u.login is not null
                and (u.type is null or u.type != 'Bot')
            )
            order by occurred_at desc, actor_login asc, kind asc
            limit ?
            """,
            (repo_id, start_s, cutoff_s, repo_id, start_s, cutoff_s, limit),
        ).fetchall()

        out = [
            RecentActivityEvent(
                kind=str(r["kind"]),
                actor_login=str(r["actor_login"]),
                occurred_at=datetime.fromisoformat(
                    str(r["occurred_at"]).replace("Z", "+00:00")
                ),
            )
            for r in rows
            if r["occurred_at"] is not None
        ]
        out.sort(key=lambda e: (e.occurred_at, e.actor_login.lower(), e.kind))
        return out
    finally:
        conn.close()


def build_pr_input_bundle(
    repo: str,
    pr_number: int,
    cutoff: datetime,
    data_dir: str | Path,
    *,
    options: PRInputBuilderOptions | None = None,
) -> PRInputBundle:
    cutoff_utc = require_dt_utc(cutoff, name="cutoff")
    opts = options or PRInputBuilderOptions()

    with HistoryReader(repo_full_name=repo, data_dir=data_dir, strict_as_of=True) as reader:
        snapshot = reader.pull_request_snapshot(number=pr_number, as_of=cutoff_utc)

    changed_files = sorted(snapshot.changed_files, key=lambda f: f.path)
    review_requests = sorted(
        snapshot.review_requests,
        key=lambda rr: (rr.reviewer_type, rr.reviewer.lower()),
    )

    parsed = parse_gate_fields(snapshot.body)
    gate_fields = PRGateFields(
        issue=parsed.issue,
        ai_disclosure=parsed.ai_disclosure,
        provenance=parsed.provenance,
        missing_issue=parsed.missing_issue,
        missing_ai_disclosure=parsed.missing_ai_disclosure,
        missing_provenance=parsed.missing_provenance,
    )

    boundary_artifact = None
    try:
        boundary_artifact = read_boundary_artifact(
            repo_full_name=repo,
            data_dir=data_dir,
            strategy_id=opts.boundary_strategy_id,
            cutoff_key=cutoff_key_utc(cutoff_utc),
        )
    except FileNotFoundError:
        if opts.boundary_required:
            raise

    if boundary_artifact is None:
        boundaries: list[str] = []
        file_boundaries: dict[str, list[str]] = {}
        file_boundary_weights: dict[str, dict[str, float]] = {}
        boundary_coverage: dict[str, object] = {
            "changed_file_count": len(changed_files),
            "covered_file_count": 0,
            "uncovered_files": [f.path for f in changed_files],
            "coverage_ratio": 0.0,
        }
        boundary_strategy = opts.boundary_strategy_id
        boundary_strategy_version = None
    else:
        footprint = project_files_to_boundary_footprint(
            paths=[f.path for f in changed_files],
            artifact=boundary_artifact,
        )
        boundaries = footprint.boundaries
        file_boundaries = footprint.file_boundaries
        file_boundary_weights = footprint.file_boundary_weights
        boundary_coverage = {
            "changed_file_count": footprint.coverage.changed_file_count,
            "covered_file_count": footprint.coverage.covered_file_count,
            "uncovered_files": footprint.coverage.uncovered_files,
            "coverage_ratio": footprint.coverage.coverage_ratio,
        }
        boundary_strategy = footprint.strategy_id
        boundary_strategy_version = footprint.strategy_version

    recent_activity: list[RecentActivityEvent] = []
    if opts.include_recent_activity:
        recent_activity = _recent_activity_window(
            repo=repo,
            data_dir=data_dir,
            cutoff=cutoff_utc,
            options=opts,
        )

    return PRInputBundle(
        repo=repo,
        pr_number=pr_number,
        cutoff=cutoff_utc,
        snapshot=snapshot,
        changed_files=changed_files,
        review_requests=review_requests,
        author_login=snapshot.author_login,
        title=snapshot.title,
        body=snapshot.body,
        gate_fields=gate_fields,
        file_boundaries=file_boundaries,
        file_boundary_weights=file_boundary_weights,
        boundaries=boundaries,
        boundary_coverage=boundary_coverage,
        boundary_strategy=boundary_strategy,
        boundary_strategy_version=boundary_strategy_version,
        recent_activity=recent_activity,
    )
