from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pyarrow as pa
import pyarrow.parquet as pq

from repo_routing.artifacts.writer import iter_pr_numbers_created_in_window
from repo_routing.exports.area import load_repo_area_overrides
from repo_routing.exports.extract import (
    PRCutoff,
    export_pr_activity_rows,
    export_pr_files_rows,
    export_pr_snapshots,
    export_pr_text_rows,
    export_prs_rows,
    export_truth_behavior_rows,
    export_truth_intent_rows,
)
from repo_routing.paths import repo_db_path


def _parse_dt(value: str) -> datetime:
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _dt_sql(dt: datetime) -> str:
    return dt.replace(tzinfo=None).isoformat(sep=" ", timespec="microseconds")


def _parse_created_at_plus_minutes(policy: str) -> int | None:
    if not policy.startswith("created_at_plus_minutes:"):
        return None
    raw = policy.split(":", 1)[1].strip()
    if not raw or not raw.isdigit():
        raise ValueError(f"invalid cutoff policy: {policy!r}")
    return int(raw)


def _cutoff_for_pr(
    *,
    conn: sqlite3.Connection,
    repo_id: int,
    pr_number: int,
    policy: str,
) -> datetime:
    pr = conn.execute(
        "select id, created_at from pull_requests where repo_id = ? and number = ?",
        (repo_id, pr_number),
    ).fetchone()
    if pr is None:
        raise KeyError(f"pr not found: {pr_number}")
    created_raw = pr["created_at"]
    if created_raw is None:
        raise RuntimeError(f"missing created_at for pr {pr_number}")
    created = _parse_dt(str(created_raw))

    if policy == "created_at":
        return created

    delta_minutes = _parse_created_at_plus_minutes(policy)
    if delta_minutes is not None:
        return created + timedelta(minutes=delta_minutes)

    if policy == "ready_for_review":
        try:
            row = conn.execute(
                """
                select min(e.occurred_at) as ready_at
                from pull_request_draft_intervals di
                join events e on e.id = di.start_event_id
                where di.pull_request_id = ?
                  and di.is_draft = 0
                  and e.occurred_at is not null
                """,
                (int(pr["id"]),),
            ).fetchone()
        except sqlite3.OperationalError:
            row = None
        if row is None or row["ready_at"] is None:
            return created
        return _parse_dt(str(row["ready_at"]))

    raise ValueError(f"unsupported cutoff policy: {policy}")


def _write_parquet(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        table = pa.Table.from_pylist(rows)
    else:
        table = pa.Table.from_pylist([{c: None for c in columns}]).slice(0, 0)
    if columns:
        table = table.select(columns)
    pq.write_table(table, path)


def _write_manifest(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True)
    path.write_text(data + "\n", encoding="utf-8")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export v0 Parquet datasets")
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--export-run-id", required=True, help="Export run id")
    parser.add_argument(
        "--cutoff-policy",
        default="created_at",
        help="created_at | ready_for_review | created_at_plus_minutes:<int>",
    )
    parser.add_argument(
        "--from",
        "--start-at",
        dest="start_at",
        help="ISO created_at window start",
    )
    parser.add_argument("--end-at", dest="end_at", help="ISO created_at window end")
    parser.add_argument(
        "--pr",
        action="append",
        type=int,
        default=[],
        help="Explicit PR number (repeatable)",
    )
    parser.add_argument(
        "--activity-lookback-days", type=int, default=180, help="Activity lookback"
    )
    parser.add_argument(
        "--truth-window-days",
        type=int,
        default=30,
        help="Window added to max(cutoff) for activity end",
    )
    parser.add_argument(
        "--intent-window-minutes",
        type=int,
        default=60,
        help="Intent truth window (minutes)",
    )
    parser.add_argument(
        "--include-text", action="store_true", help="Write prs_text.parquet"
    )
    parser.add_argument(
        "--include-truth",
        action="store_true",
        help="Write truth_behavior.parquet and truth_intent.parquet",
    )
    parser.add_argument("--data-dir", default="data", help="Base data dir")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    repo = args.repo
    data_dir = Path(args.data_dir)
    owner, name = repo.split("/", 1)
    export_dir = data_dir / "exports" / owner / name / args.export_run_id

    pr_numbers: list[int]
    if args.pr:
        pr_numbers = sorted(set(args.pr))
    else:
        start_at = _parse_dt(args.start_at) if args.start_at else None
        end_at = _parse_dt(args.end_at) if args.end_at else None
        pr_numbers = list(
            iter_pr_numbers_created_in_window(
                repo=repo,
                data_dir=data_dir,
                start_at=start_at,
                end_at=end_at,
            )
        )

    if not pr_numbers:
        raise SystemExit("no PRs selected for export")

    db = repo_db_path(repo_full_name=repo, data_dir=data_dir)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "select id from repos where full_name = ?", (repo,)
        ).fetchone()
        if row is None:
            raise SystemExit(f"repo not found: {repo}")
        repo_id = int(row["id"])

        pr_cutoffs: list[PRCutoff] = [
            PRCutoff(
                pr_number=n,
                cutoff=_cutoff_for_pr(
                    conn=conn, repo_id=repo_id, pr_number=n, policy=args.cutoff_policy
                ),
                cutoff_policy=args.cutoff_policy,
            )
            for n in pr_numbers
        ]
    finally:
        conn.close()

    min_cutoff = min(c.cutoff for c in pr_cutoffs)
    max_cutoff = max(c.cutoff for c in pr_cutoffs)
    activity_start = min_cutoff - timedelta(days=args.activity_lookback_days)
    activity_end = max_cutoff + timedelta(days=args.truth_window_days)

    snapshots = export_pr_snapshots(
        repo=repo, data_dir=data_dir, pr_cutoffs=pr_cutoffs
    )
    overrides = load_repo_area_overrides(repo_full_name=repo, data_dir=data_dir)

    prs_rows = export_prs_rows(snapshots)
    pr_files_rows = export_pr_files_rows(snapshots, area_overrides=overrides)
    pr_activity_rows = export_pr_activity_rows(
        repo=repo, data_dir=data_dir, start_at=activity_start, end_at=activity_end
    )

    _write_parquet(
        export_dir / "prs.parquet",
        prs_rows,
        [
            "repo",
            "pr_number",
            "cutoff",
            "cutoff_policy",
            "export_version",
            "author_login",
            "created_at",
            "base_sha",
            "head_sha",
            "n_changed_files",
            "missing_issue",
            "missing_ai_disclosure",
            "missing_provenance",
        ],
    )

    if args.include_text:
        prs_text_rows = export_pr_text_rows(snapshots)
        _write_parquet(
            export_dir / "prs_text.parquet",
            prs_text_rows,
            ["repo", "pr_number", "cutoff", "export_version", "title", "body"],
        )

    _write_parquet(
        export_dir / "pr_files.parquet",
        pr_files_rows,
        [
            "repo",
            "pr_number",
            "cutoff",
            "head_sha",
            "path",
            "status",
            "additions",
            "deletions",
            "changes",
            "default_area",
        ],
    )

    _write_parquet(
        export_dir / "pr_activity.parquet",
        pr_activity_rows,
        [
            "repo",
            "pr_number",
            "occurred_at",
            "actor_login",
            "actor_type",
            "kind",
            "path",
            "review_state",
        ],
    )

    if args.include_truth:
        truth_behavior = export_truth_behavior_rows(
            repo=repo, data_dir=data_dir, pr_cutoffs=pr_cutoffs
        )
        truth_intent = export_truth_intent_rows(
            repo=repo,
            data_dir=data_dir,
            pr_cutoffs=pr_cutoffs,
            intent_window=timedelta(minutes=args.intent_window_minutes),
        )
        _write_parquet(
            export_dir / "truth_behavior.parquet",
            truth_behavior,
            [
                "repo",
                "pr_number",
                "cutoff",
                "export_version",
                "truth_behavior_first_reviewer",
            ],
        )
        _write_parquet(
            export_dir / "truth_intent.parquet",
            truth_intent,
            [
                "repo",
                "pr_number",
                "cutoff",
                "export_version",
                "requested_at",
                "target_type",
                "target_name",
            ],
        )

    manifest = {
        "repo": repo,
        "export_run_id": args.export_run_id,
        "export_version": "v0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cutoff_policy": args.cutoff_policy,
        "activity_lookback_days": args.activity_lookback_days,
        "activity_start": activity_start.isoformat(),
        "activity_end": activity_end.isoformat(),
        "truth_window_days": args.truth_window_days,
        "intent_window_minutes": args.intent_window_minutes,
        "include_text": bool(args.include_text),
        "include_truth": bool(args.include_truth),
        "pr_numbers": pr_numbers,
        "start_at": args.start_at,
        "end_at": args.end_at,
        "data_dir": str(data_dir),
    }
    _write_manifest(export_dir / "export_manifest.json", manifest)

    print(str(export_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
