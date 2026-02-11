from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from repo_routing.paths import repo_db_path

from .models import TruthDiagnostics, TruthStatus
from .truth_policy import TruthPolicySpec


def _parse_dt(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    s = str(value)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _dt_sql(dt: datetime) -> str:
    return dt.replace(tzinfo=None).isoformat(sep=" ")


def _is_bot_login(login: str) -> bool:
    # Best-effort; canonical bot detection uses users.type when available.
    return login.lower().endswith("[bot]")


def _truth_coverage_horizon_max(conn: sqlite3.Connection, *, repo_id: int) -> datetime | None:
    values: list[datetime] = []

    row = conn.execute(
        "select max(occurred_at) as max_at from events where repo_id = ?",
        (repo_id,),
    ).fetchone()
    if row is not None:
        dt = _parse_dt(row["max_at"])
        if dt is not None:
            values.append(dt)

    row = conn.execute(
        "select max(submitted_at) as max_at from reviews where repo_id = ?",
        (repo_id,),
    ).fetchone()
    if row is not None:
        dt = _parse_dt(row["max_at"])
        if dt is not None:
            values.append(dt)

    row = conn.execute(
        "select max(created_at) as max_at from comments where repo_id = ?",
        (repo_id,),
    ).fetchone()
    if row is not None:
        dt = _parse_dt(row["max_at"])
        if dt is not None:
            values.append(dt)

    if not values:
        return None
    return max(values)


def _truth_gap_resources(conn: sqlite3.Connection, *, repo_id: int) -> list[str]:
    relevant = {
        "reviews",
        "review_comments",
        "issue_comments",
        "issue_events",
        "pulls",
        "issues",
    }
    try:
        rows = conn.execute(
            """
            select distinct resource
            from ingestion_gaps
            where repo_id = ?
            order by resource asc
            """,
            (repo_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        return []

    resources = [str(r["resource"]) for r in rows if r["resource"] is not None]
    return [r for r in resources if r in relevant]


def behavior_truth_with_diagnostics(
    *,
    repo: str,
    pr_number: int,
    cutoff: datetime,
    data_dir: str | Path = "data",
    exclude_author: bool = True,
    exclude_bots: bool = True,
    window: timedelta = timedelta(hours=48),
    include_review_comments: bool = True,
    review_states: set[str] | None = None,
    policy_id: str = "first_response_v1",
    policy_version: str = "v1",
) -> TruthDiagnostics:
    """Behavior truth with explicit coverage diagnostics."""

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

        pr = conn.execute(
            "select id, user_id from pull_requests where repo_id = ? and number = ?",
            (repo_id, pr_number),
        ).fetchone()
        if pr is None:
            raise KeyError(f"pr not found: {repo}#{pr_number}")

        pr_id = int(pr["id"])
        author_id = pr["user_id"]

        cutoff_s = _dt_sql(cutoff)
        window_end = cutoff + window
        end_s = _dt_sql(window_end)

        review_rows = conn.execute(
            """
            select r.user_id as user_id,
                   u.login as login,
                   u.type as type,
                   r.state as review_state,
                   r.submitted_at as ts,
                   r.id as event_id,
                   'review_submitted' as kind
            from reviews r
            join users u on u.id = r.user_id
            where r.repo_id = ?
              and r.pull_request_id = ?
              and r.submitted_at is not null
              and r.submitted_at > ?
              and r.submitted_at <= ?
              and u.login is not null
            """,
            (repo_id, pr_id, cutoff_s, end_s),
        ).fetchall()

        review_comment_rows: list[sqlite3.Row] = []
        if include_review_comments:
            try:
                review_comment_rows = conn.execute(
                    """
                    select c.user_id as user_id,
                           u.login as login,
                           u.type as type,
                           c.created_at as ts,
                           c.id as event_id,
                           'review_comment' as kind
                    from comments c
                    join users u on u.id = c.user_id
                    where c.repo_id = ?
                      and c.pull_request_id = ?
                      and c.review_id is not null
                      and c.created_at is not null
                      and c.created_at > ?
                      and c.created_at <= ?
                      and u.login is not null
                    """,
                    (repo_id, pr_id, cutoff_s, end_s),
                ).fetchall()
            except sqlite3.OperationalError:
                review_comment_rows = []

        rows = sorted(
            [*review_rows, *review_comment_rows],
            key=lambda r: (str(r["ts"]), int(r["event_id"]), str(r["kind"])),
        )

        selected: str | None = None
        selected_source: str | None = None
        selected_event_id: int | None = None
        eligible = 0
        for r in rows:
            if exclude_bots and (r["type"] == "Bot" or _is_bot_login(str(r["login"]))):
                continue
            if exclude_author and author_id is not None and r["user_id"] == author_id:
                continue
            if review_states is not None and str(r["kind"]) == "review_submitted":
                state = str(r["review_state"] or "").upper()
                if state not in review_states:
                    continue
            eligible += 1
            if selected is None:
                selected = str(r["login"])
                selected_source = str(r["kind"])
                selected_event_id = int(r["event_id"])

        horizon_max = _truth_coverage_horizon_max(conn, repo_id=repo_id)
        horizon_complete = horizon_max is not None and horizon_max >= window_end
        gap_resources = _truth_gap_resources(conn, repo_id=repo_id)
        coverage_complete = bool(horizon_complete and not gap_resources)

        notes: list[str] = []
        if horizon_max is None:
            notes.append("truth coverage horizon unavailable")
        elif not horizon_complete:
            notes.append("truth window extends beyond ingested horizon")
        if gap_resources:
            notes.append("ingestion gaps present for truth-related resources")
        if review_states:
            notes.append(
                "review-state filter="
                + ",".join(sorted({s.upper() for s in review_states}, key=str.lower))
            )
        if include_review_comments:
            notes.append("truth scans review_submitted + review_comment")
        else:
            notes.append("truth scans review_submitted only")

        if selected is not None:
            status = TruthStatus.observed
        elif coverage_complete:
            status = TruthStatus.no_post_cutoff_response
        else:
            status = TruthStatus.unknown_due_to_ingestion_gap

        return TruthDiagnostics(
            repo=repo,
            pr_number=pr_number,
            cutoff=cutoff,
            window_end=window_end,
            status=status,
            policy_id=policy_id,
            policy_version=policy_version,
            selected_login=selected,
            selected_source=selected_source,
            selected_event_id=selected_event_id,
            include_review_comments=include_review_comments,
            scanned_review_rows=len(review_rows),
            scanned_review_comment_rows=len(review_comment_rows),
            eligible_candidates=eligible,
            coverage_complete=coverage_complete,
            coverage_horizon_max=horizon_max,
            gap_resources=gap_resources,
            notes=notes,
        )
    finally:
        conn.close()


def behavior_truth_first_eligible_review(
    *,
    repo: str,
    pr_number: int,
    cutoff: datetime,
    data_dir: str | Path = "data",
    exclude_author: bool = True,
    exclude_bots: bool = True,
    window: timedelta = timedelta(hours=48),
    include_review_comments: bool = True,
) -> str | None:
    diagnostics = behavior_truth_with_diagnostics(
        repo=repo,
        pr_number=pr_number,
        cutoff=cutoff,
        data_dir=data_dir,
        exclude_author=exclude_author,
        exclude_bots=exclude_bots,
        window=window,
        include_review_comments=include_review_comments,
    )
    return diagnostics.selected_login


def truth_with_policy(
    *,
    policy: TruthPolicySpec,
    repo: str,
    pr_number: int,
    cutoff: datetime,
    data_dir: str | Path = "data",
    exclude_author: bool = True,
    exclude_bots: bool = True,
) -> TruthDiagnostics:
    window = timedelta(seconds=policy.window_seconds)
    policy_id = policy.id

    if policy_id == "first_response_v1":
        return behavior_truth_with_diagnostics(
            repo=repo,
            pr_number=pr_number,
            cutoff=cutoff,
            data_dir=data_dir,
            exclude_author=exclude_author,
            exclude_bots=exclude_bots,
            window=window,
            include_review_comments=True,
            policy_id=policy.id,
            policy_version=policy.version,
        )

    if policy_id == "first_approval_v1":
        return behavior_truth_with_diagnostics(
            repo=repo,
            pr_number=pr_number,
            cutoff=cutoff,
            data_dir=data_dir,
            exclude_author=exclude_author,
            exclude_bots=exclude_bots,
            window=window,
            include_review_comments=False,
            review_states={"APPROVED"},
            policy_id=policy.id,
            policy_version=policy.version,
        )

    # Stubbed readiness-gated policies remain unavailable until ingestion readiness
    # is explicitly implemented.
    return TruthDiagnostics(
        repo=repo,
        pr_number=pr_number,
        cutoff=cutoff,
        window_end=cutoff + window,
        status=TruthStatus.policy_unavailable,
        policy_id=policy.id,
        policy_version=policy.version,
        selected_login=None,
        selected_source=None,
        selected_event_id=None,
        include_review_comments=False,
        scanned_review_rows=0,
        scanned_review_comment_rows=0,
        eligible_candidates=0,
        coverage_complete=False,
        coverage_horizon_max=None,
        gap_resources=[],
        notes=["policy readiness gate is closed"],
    )


def intent_truth_from_review_requests(
    *,
    repo: str,
    pr_number: int,
    cutoff: datetime,
    window: timedelta = timedelta(minutes=60),
    data_dir: str | Path = "data",
) -> list[str]:
    """v0 intent truth: review requests active at cutoff within a fixed window.

    This reads from the PR review_request interval table (as-of safety).
    """

    # For v0, we interpret the rule as: look at review requests active at cutoff
    # and include them if the review-request interval started within [cutoff-window, cutoff].
    start = cutoff - window

    db = repo_db_path(repo_full_name=repo, data_dir=data_dir)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        pr_row = conn.execute(
            """
            select pr.id as pr_id
            from pull_requests pr
            join repos r on r.id = pr.repo_id
            where r.full_name = ? and pr.number = ?
            """,
            (repo, pr_number),
        ).fetchone()
        if pr_row is None:
            raise KeyError(f"pr not found: {repo}#{pr_number}")

        pr_id = int(pr_row["pr_id"])

        cutoff_s = _dt_sql(cutoff)
        start_s = _dt_sql(start)
        rows = conn.execute(
            """
            select rri.reviewer_type as reviewer_type,
                   rri.reviewer_id as reviewer_id,
                   se.occurred_at as start_at
            from pull_request_review_request_intervals rri
            join events se on se.id = rri.start_event_id
            left join events ee on ee.id = rri.end_event_id
            where rri.pull_request_id = ?
              and se.occurred_at <= ?
              and (ee.id is null or ? < ee.occurred_at)
              and se.occurred_at >= ?
            order by rri.reviewer_type asc, rri.reviewer_id asc
            """,
            (pr_id, cutoff_s, cutoff_s, start_s),
        ).fetchall()

        out: list[str] = []
        for rr in rows:
            if rr["reviewer_type"] == "Team":
                team = conn.execute(
                    "select slug from teams where id = ?", (int(rr["reviewer_id"]),)
                ).fetchone()
                if team is None or team["slug"] is None:
                    continue
                out.append(f"team:{team['slug']}")
            else:
                user = conn.execute(
                    "select login, type from users where id = ?",
                    (int(rr["reviewer_id"]),),
                ).fetchone()
                if user is None or user["login"] is None:
                    continue
                if user["type"] == "Bot":
                    continue
                out.append(f"user:{user['login']}")

        # stable, deterministic
        return sorted(set(out), key=lambda s: s.lower())
    finally:
        conn.close()
