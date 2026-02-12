from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from ..history.models import PullRequestSnapshot
from ..history.reader import HistoryReader
from ..parsing.gates import parse_gate_fields
from ..paths import repo_db_path
from .boundary import BoundaryOverride, boundary_for_path


def _parse_dt(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def _dt_sql(dt: datetime) -> str:
    return dt.replace(tzinfo=None).isoformat(sep=" ", timespec="microseconds")


def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    dt = value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _is_bot_login(login: str) -> bool:
    return login.lower().endswith("[bot]")


@dataclass(frozen=True)
class PRCutoff:
    pr_number: int
    cutoff: datetime
    cutoff_policy: str


@dataclass(frozen=True)
class PRSnapshotWithCutoff:
    pr_number: int
    cutoff: datetime
    cutoff_policy: str
    snapshot: PullRequestSnapshot


def export_pr_snapshots(
    *,
    repo: str,
    data_dir: str | Path,
    pr_cutoffs: Iterable[PRCutoff],
    strict_as_of: bool = True,
) -> list[PRSnapshotWithCutoff]:
    ordered = sorted(pr_cutoffs, key=lambda c: c.pr_number)
    out: list[PRSnapshotWithCutoff] = []
    with HistoryReader(
        repo_full_name=repo, data_dir=data_dir, strict_as_of=strict_as_of
    ) as reader:
        for c in ordered:
            snap = reader.pull_request_snapshot(number=c.pr_number, as_of=c.cutoff)
            out.append(
                PRSnapshotWithCutoff(
                    pr_number=c.pr_number,
                    cutoff=c.cutoff,
                    cutoff_policy=c.cutoff_policy,
                    snapshot=snap,
                )
            )
    return out


def export_prs_rows(
    snapshots: Iterable[PRSnapshotWithCutoff],
    *,
    export_version: str = "v0",
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in snapshots:
        pr = item.snapshot
        gates = parse_gate_fields(pr.body)
        rows.append(
            {
                "repo": pr.repo,
                "pr_number": pr.number,
                "cutoff": _to_iso(item.cutoff),
                "cutoff_policy": item.cutoff_policy,
                "export_version": export_version,
                "author_login": pr.author_login,
                "created_at": _to_iso(pr.created_at),
                "base_sha": pr.base_sha,
                "head_sha": pr.head_sha,
                "n_changed_files": len(pr.changed_files),
                "missing_issue": gates.missing_issue,
                "missing_ai_disclosure": gates.missing_ai_disclosure,
                "missing_provenance": gates.missing_provenance,
            }
        )
    rows.sort(key=lambda r: int(r["pr_number"]))
    return rows


def export_pr_text_rows(
    snapshots: Iterable[PRSnapshotWithCutoff],
    *,
    export_version: str = "v0",
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in snapshots:
        pr = item.snapshot
        rows.append(
            {
                "repo": pr.repo,
                "pr_number": pr.number,
                "cutoff": _to_iso(item.cutoff),
                "export_version": export_version,
                "title": pr.title,
                "body": pr.body,
            }
        )
    rows.sort(key=lambda r: int(r["pr_number"]))
    return rows


def export_pr_files_rows(
    snapshots: Iterable[PRSnapshotWithCutoff],
    *,
    export_version: str = "v0",
    boundary_overrides: list[BoundaryOverride] | None = None,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in snapshots:
        pr = item.snapshot
        for f in pr.changed_files:
            rows.append(
                {
                    "repo": pr.repo,
                    "pr_number": pr.number,
                    "cutoff": _to_iso(item.cutoff),
                    "head_sha": pr.head_sha,
                    "path": f.path,
                    "status": f.status,
                    "additions": f.additions,
                    "deletions": f.deletions,
                    "changes": f.changes,
                    "default_boundary": boundary_for_path(f.path, boundary_overrides),
                }
            )
    rows.sort(key=lambda r: (int(r["pr_number"]), str(r["path"])))
    return rows


def export_pr_activity_rows(
    *,
    repo: str,
    data_dir: str | Path,
    start_at: datetime,
    end_at: datetime,
) -> list[dict[str, object]]:
    db = repo_db_path(repo_full_name=repo, data_dir=data_dir)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "select id from repos where full_name = ?", (repo,)
        ).fetchone()
        if row is None:
            raise KeyError(f"repo not found in db: {repo}")
        repo_id = int(row["id"])

        start_s = _dt_sql(start_at)
        end_s = _dt_sql(end_at)

        rows: list[dict[str, object]] = []

        review_rows = conn.execute(
            """
            select r.id as row_id,
                   pr.number as pr_number,
                   r.submitted_at as occurred_at,
                   u.login as actor_login,
                   u.type as actor_type,
                   r.state as review_state
            from reviews r
            join pull_requests pr on pr.id = r.pull_request_id
            join users u on u.id = r.user_id
            where r.repo_id = ?
              and r.submitted_at is not null
              and r.submitted_at >= ?
              and r.submitted_at <= ?
              and u.login is not null
            order by r.submitted_at asc, pr.number asc, lower(u.login) asc, r.id asc
            """,
            (repo_id, start_s, end_s),
        ).fetchall()

        for r in review_rows:
            rows.append(
                {
                    "repo": repo,
                    "pr_number": int(r["pr_number"]),
                    "occurred_at": _to_iso(_parse_dt(r["occurred_at"])),
                    "actor_login": str(r["actor_login"]),
                    "actor_type": r["actor_type"],
                    "kind": "review_submitted",
                    "path": None,
                    "review_state": r["review_state"],
                }
            )

        comment_rows = conn.execute(
            """
            select c.id as row_id,
                   pr.number as pr_number,
                   c.created_at as occurred_at,
                   u.login as actor_login,
                   u.type as actor_type,
                   c.path as path,
                   c.comment_type as comment_type,
                   c.review_id as review_id
            from comments c
            join pull_requests pr on pr.id = c.pull_request_id
            join users u on u.id = c.user_id
            where c.repo_id = ?
              and c.pull_request_id is not null
              and c.created_at is not null
              and c.created_at >= ?
              and c.created_at <= ?
              and u.login is not null
            order by c.created_at asc, pr.number asc, lower(u.login) asc, c.id asc
            """,
            (repo_id, start_s, end_s),
        ).fetchall()

        for r in comment_rows:
            comment_type = r["comment_type"]
            kind = "comment_created"
            if comment_type == "review" or r["review_id"] is not None:
                kind = "review_comment_created"
            rows.append(
                {
                    "repo": repo,
                    "pr_number": int(r["pr_number"]),
                    "occurred_at": _to_iso(_parse_dt(r["occurred_at"])),
                    "actor_login": str(r["actor_login"]),
                    "actor_type": r["actor_type"],
                    "kind": kind,
                    "path": r["path"],
                    "review_state": None,
                }
            )

        rows.sort(
            key=lambda r: (
                str(r["occurred_at"] or ""),
                int(r["pr_number"]),
                str(r["kind"]),
                str(r["actor_login"]).lower(),
                str(r.get("path") or ""),
            )
        )
        return rows
    finally:
        conn.close()


def export_truth_behavior_rows(
    *,
    repo: str,
    data_dir: str | Path,
    pr_cutoffs: Iterable[PRCutoff],
    export_version: str = "v0",
    exclude_author: bool = True,
    exclude_bots: bool = True,
) -> list[dict[str, object]]:
    db = repo_db_path(repo_full_name=repo, data_dir=data_dir)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "select id from repos where full_name = ?", (repo,)
        ).fetchone()
        if row is None:
            raise KeyError(f"repo not found in db: {repo}")
        repo_id = int(row["id"])

        ordered = sorted(pr_cutoffs, key=lambda c: c.pr_number)
        out: list[dict[str, object]] = []
        for c in ordered:
            pr = conn.execute(
                "select id, user_id from pull_requests where repo_id = ? and number = ?",
                (repo_id, c.pr_number),
            ).fetchone()
            if pr is None:
                raise KeyError(f"pr not found: {repo}#{c.pr_number}")
            pr_id = int(pr["id"])
            author_id = pr["user_id"]

            cutoff_s = _dt_sql(c.cutoff)
            rows = conn.execute(
                """
                select r.user_id as user_id,
                       u.login as login,
                       u.type as type,
                       r.submitted_at as submitted_at
                from reviews r
                join users u on u.id = r.user_id
                where r.repo_id = ?
                  and r.pull_request_id = ?
                  and r.submitted_at is not null
                  and r.submitted_at > ?
                  and u.login is not null
                order by r.submitted_at asc, r.id asc
                """,
                (repo_id, pr_id, cutoff_s),
            ).fetchall()

            chosen: str | None = None
            for r in rows:
                login = str(r["login"])
                if exclude_bots and (
                    r["type"] == "Bot" or _is_bot_login(login)
                ):
                    continue
                if exclude_author and author_id is not None and r["user_id"] == author_id:
                    continue
                chosen = login
                break

            out.append(
                {
                    "repo": repo,
                    "pr_number": c.pr_number,
                    "cutoff": _to_iso(c.cutoff),
                    "export_version": export_version,
                    "truth_behavior_first_reviewer": chosen,
                }
            )
        return out
    finally:
        conn.close()


def export_truth_intent_rows(
    *,
    repo: str,
    data_dir: str | Path,
    pr_cutoffs: Iterable[PRCutoff],
    export_version: str = "v0",
    intent_window: timedelta = timedelta(minutes=60),
) -> list[dict[str, object]]:
    db = repo_db_path(repo_full_name=repo, data_dir=data_dir)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "select id from repos where full_name = ?", (repo,)
        ).fetchone()
        if row is None:
            raise KeyError(f"repo not found in db: {repo}")
        repo_id = int(row["id"])

        ordered = sorted(pr_cutoffs, key=lambda c: c.pr_number)
        out: list[dict[str, object]] = []
        for c in ordered:
            pr = conn.execute(
                "select id from pull_requests where repo_id = ? and number = ?",
                (repo_id, c.pr_number),
            ).fetchone()
            if pr is None:
                raise KeyError(f"pr not found: {repo}#{c.pr_number}")
            pr_id = int(pr["id"])

            start_s = _dt_sql(c.cutoff)
            end_s = _dt_sql(c.cutoff + intent_window)
            rows = conn.execute(
                """
                select rri.reviewer_type as reviewer_type,
                       rri.reviewer_id as reviewer_id,
                       se.occurred_at as requested_at
                from pull_request_review_request_intervals rri
                join events se on se.id = rri.start_event_id
                where rri.pull_request_id = ?
                  and se.occurred_at >= ?
                  and se.occurred_at <= ?
                order by se.occurred_at asc, rri.reviewer_type asc, rri.reviewer_id asc
                """,
                (pr_id, start_s, end_s),
            ).fetchall()

            for rr in rows:
                reviewer_type = rr["reviewer_type"]
                if reviewer_type == "Team":
                    team = conn.execute(
                        "select slug from teams where id = ?",
                        (int(rr["reviewer_id"]),),
                    ).fetchone()
                    if team is None or team["slug"] is None:
                        continue
                    target_type = "team"
                    target_name = str(team["slug"])
                else:
                    user = conn.execute(
                        "select login, type from users where id = ?",
                        (int(rr["reviewer_id"]),),
                    ).fetchone()
                    if user is None or user["login"] is None:
                        continue
                    if user["type"] == "Bot":
                        continue
                    target_type = "user"
                    target_name = str(user["login"])

                out.append(
                    {
                        "repo": repo,
                        "pr_number": c.pr_number,
                        "cutoff": _to_iso(c.cutoff),
                        "export_version": export_version,
                        "requested_at": _to_iso(_parse_dt(rr["requested_at"])),
                        "target_type": target_type,
                        "target_name": target_name,
                    }
                )
        out.sort(
            key=lambda r: (
                str(r["requested_at"] or ""),
                str(r["target_type"]),
                str(r["target_name"]).lower(),
                int(r["pr_number"]),
            )
        )
        return out
    finally:
        conn.close()
