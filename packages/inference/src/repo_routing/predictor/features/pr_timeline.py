from __future__ import annotations

import re
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from ...inputs.models import PRInputBundle
from .patterns import WIP_TITLE_HINTS
from .schemas import FeatureExtractionContext
from .sql import (
    active_review_request_counts,
    comment_counts_pre_cutoff,
    connect_repo_db,
    count_head_updates_pre_cutoff,
    cutoff_sql,
    is_draft_at_cutoff as sql_is_draft_at_cutoff,
    latest_author_activity_pre_cutoff,
    latest_head_update_pre_cutoff,
    load_repo_pr_ids,
    review_count_pre_cutoff as sql_review_count_pre_cutoff,
)


def is_draft_at_cutoff(ctx: FeatureExtractionContext) -> bool:
    conn = connect_repo_db(repo=ctx.repo, data_dir=ctx.data_dir)
    try:
        ids = load_repo_pr_ids(conn=conn, repo=ctx.repo, pr_number=ctx.pr_number)
        return sql_is_draft_at_cutoff(
            conn=conn,
            pull_request_id=ids.pull_request_id,
            cutoff=ctx.cutoff,
        )
    finally:
        conn.close()


def pr_age_seconds_at_cutoff(input: PRInputBundle) -> float:
    created_at = input.snapshot.created_at
    if created_at is None:
        return 0.0
    return max(0.0, (input.cutoff - created_at).total_seconds())


def time_since_last_head_update_seconds(ctx: FeatureExtractionContext) -> float | None:
    conn = connect_repo_db(repo=ctx.repo, data_dir=ctx.data_dir)
    try:
        ids = load_repo_pr_ids(conn=conn, repo=ctx.repo, pr_number=ctx.pr_number)
        ts = latest_head_update_pre_cutoff(
            conn=conn,
            pull_request_id=ids.pull_request_id,
            cutoff=ctx.cutoff,
        )
    finally:
        conn.close()
    return _seconds_between(ctx.cutoff, ts)


def head_updates_pre_cutoff_count(ctx: FeatureExtractionContext) -> int:
    conn = connect_repo_db(repo=ctx.repo, data_dir=ctx.data_dir)
    try:
        ids = load_repo_pr_ids(conn=conn, repo=ctx.repo, pr_number=ctx.pr_number)
        return count_head_updates_pre_cutoff(
            conn=conn,
            pull_request_id=ids.pull_request_id,
            cutoff=ctx.cutoff,
        )
    finally:
        conn.close()


def head_updates_in_window_count(ctx: FeatureExtractionContext, *, days: int) -> int:
    conn = connect_repo_db(repo=ctx.repo, data_dir=ctx.data_dir)
    try:
        ids = load_repo_pr_ids(conn=conn, repo=ctx.repo, pr_number=ctx.pr_number)
        start = cutoff_sql(ctx.cutoff - timedelta(days=days))
        cutoff_s = cutoff_sql(ctx.cutoff)
        row = conn.execute(
            """
            select count(*) as n
            from pull_request_head_intervals phi
            join events se on se.id = phi.start_event_id
            where phi.pull_request_id = ?
              and se.occurred_at >= ?
              and se.occurred_at <= ?
            """,
            (ids.pull_request_id, start, cutoff_s),
        ).fetchone()
        return 0 if row is None else int(row["n"])
    finally:
        conn.close()


def head_update_burstiness_last_6h(ctx: FeatureExtractionContext) -> float:
    conn = connect_repo_db(repo=ctx.repo, data_dir=ctx.data_dir)
    try:
        ids = load_repo_pr_ids(conn=conn, repo=ctx.repo, pr_number=ctx.pr_number)
        start = cutoff_sql(ctx.cutoff - timedelta(hours=6))
        cutoff_s = cutoff_sql(ctx.cutoff)
        row_recent = conn.execute(
            """
            select count(*) as n
            from pull_request_head_intervals phi
            join events se on se.id = phi.start_event_id
            where phi.pull_request_id = ?
              and se.occurred_at >= ?
              and se.occurred_at <= ?
            """,
            (ids.pull_request_id, start, cutoff_s),
        ).fetchone()
        row_all = conn.execute(
            """
            select count(*) as n
            from pull_request_head_intervals phi
            join events se on se.id = phi.start_event_id
            where phi.pull_request_id = ?
              and se.occurred_at <= ?
            """,
            (ids.pull_request_id, cutoff_s),
        ).fetchone()
    finally:
        conn.close()

    recent = 0 if row_recent is None else int(row_recent["n"])
    total = 0 if row_all is None else int(row_all["n"])
    if total <= 0:
        return 0.0
    return float(recent) / float(total)


def last_author_activity_pre_cutoff_seconds(ctx: FeatureExtractionContext) -> float | None:
    conn = connect_repo_db(repo=ctx.repo, data_dir=ctx.data_dir)
    try:
        ids = load_repo_pr_ids(conn=conn, repo=ctx.repo, pr_number=ctx.pr_number)
        ts = latest_author_activity_pre_cutoff(
            conn=conn,
            repo_id=ids.repo_id,
            pull_request_id=ids.pull_request_id,
            author_id=ids.author_id,
            cutoff=ctx.cutoff,
        )
    finally:
        conn.close()
    return _seconds_between(ctx.cutoff, ts)


def author_comment_count_pre_cutoff(ctx: FeatureExtractionContext) -> int:
    conn = connect_repo_db(repo=ctx.repo, data_dir=ctx.data_dir)
    try:
        ids = load_repo_pr_ids(conn=conn, repo=ctx.repo, pr_number=ctx.pr_number)
        author_n, _ = comment_counts_pre_cutoff(
            conn=conn,
            repo_id=ids.repo_id,
            pull_request_id=ids.pull_request_id,
            author_id=ids.author_id,
            cutoff=ctx.cutoff,
        )
        return author_n
    finally:
        conn.close()


def non_author_comment_count_pre_cutoff(ctx: FeatureExtractionContext) -> int:
    conn = connect_repo_db(repo=ctx.repo, data_dir=ctx.data_dir)
    try:
        ids = load_repo_pr_ids(conn=conn, repo=ctx.repo, pr_number=ctx.pr_number)
        _, non_author_n = comment_counts_pre_cutoff(
            conn=conn,
            repo_id=ids.repo_id,
            pull_request_id=ids.pull_request_id,
            author_id=ids.author_id,
            cutoff=ctx.cutoff,
        )
        return non_author_n
    finally:
        conn.close()


def review_count_pre_cutoff(ctx: FeatureExtractionContext) -> int:
    conn = connect_repo_db(repo=ctx.repo, data_dir=ctx.data_dir)
    try:
        ids = load_repo_pr_ids(conn=conn, repo=ctx.repo, pr_number=ctx.pr_number)
        return sql_review_count_pre_cutoff(
            conn=conn,
            repo_id=ids.repo_id,
            pull_request_id=ids.pull_request_id,
            cutoff=ctx.cutoff,
        )
    finally:
        conn.close()


def review_state_counts_pre_cutoff(ctx: FeatureExtractionContext) -> dict[str, int]:
    conn = connect_repo_db(repo=ctx.repo, data_dir=ctx.data_dir)
    try:
        ids = load_repo_pr_ids(conn=conn, repo=ctx.repo, pr_number=ctx.pr_number)
        try:
            rows = conn.execute(
                """
                select lower(coalesce(rci.state, 'commented')) as state, count(*) as n
                from review_content_intervals rci
                join reviews r on r.id = rci.review_id
                join events se on se.id = rci.start_event_id
                left join events ee on ee.id = rci.end_event_id
                where r.repo_id = ?
                  and r.pull_request_id = ?
                  and se.occurred_at <= ?
                  and (ee.id is null or ? < ee.occurred_at)
                group by lower(coalesce(rci.state, 'commented'))
                """,
                (ids.repo_id, ids.pull_request_id, cutoff_sql(ctx.cutoff), cutoff_sql(ctx.cutoff)),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []
    finally:
        conn.close()

    out = {"approve": 0, "comment": 0, "changes_requested": 0}
    for row in rows:
        raw = str(row["state"])
        n = int(row["n"])
        if "approv" in raw:
            out["approve"] += n
        elif "request" in raw or "changes" in raw:
            out["changes_requested"] += n
        else:
            out["comment"] += n
    return out


def unique_participants_count(ctx: FeatureExtractionContext) -> int:
    conn = connect_repo_db(repo=ctx.repo, data_dir=ctx.data_dir)
    try:
        ids = load_repo_pr_ids(conn=conn, repo=ctx.repo, pr_number=ctx.pr_number)
        rows = conn.execute(
            """
            select lower(login) as login from (
              select u.login as login
              from comments c
              join users u on u.id = c.user_id
              where c.repo_id = ? and c.pull_request_id = ? and c.created_at <= ? and u.login is not null
              union
              select u.login as login
              from reviews r
              join users u on u.id = r.user_id
              where r.repo_id = ? and r.pull_request_id = ? and r.submitted_at <= ? and u.login is not null
            )
            """,
            (
                ids.repo_id,
                ids.pull_request_id,
                cutoff_sql(ctx.cutoff),
                ids.repo_id,
                ids.pull_request_id,
                cutoff_sql(ctx.cutoff),
            ),
        ).fetchall()
    finally:
        conn.close()
    return len({str(r["login"]).lower() for r in rows if r["login"] is not None})


def any_active_review_requests_at_cutoff(ctx: FeatureExtractionContext) -> bool:
    users_n = requested_users_count_at_cutoff(ctx)
    teams_n = requested_teams_count_at_cutoff(ctx)
    return users_n + teams_n > 0


def requested_users_count_at_cutoff(ctx: FeatureExtractionContext) -> int:
    conn = connect_repo_db(repo=ctx.repo, data_dir=ctx.data_dir)
    try:
        ids = load_repo_pr_ids(conn=conn, repo=ctx.repo, pr_number=ctx.pr_number)
        users_n, _teams_n = active_review_request_counts(
            conn=conn,
            pull_request_id=ids.pull_request_id,
            cutoff=ctx.cutoff,
        )
        return users_n
    finally:
        conn.close()


def requested_teams_count_at_cutoff(ctx: FeatureExtractionContext) -> int:
    conn = connect_repo_db(repo=ctx.repo, data_dir=ctx.data_dir)
    try:
        ids = load_repo_pr_ids(conn=conn, repo=ctx.repo, pr_number=ctx.pr_number)
        _users_n, teams_n = active_review_request_counts(
            conn=conn,
            pull_request_id=ids.pull_request_id,
            cutoff=ctx.cutoff,
        )
        return teams_n
    finally:
        conn.close()


def request_event_add_remove_counts(ctx: FeatureExtractionContext) -> tuple[int, int]:
    conn = connect_repo_db(repo=ctx.repo, data_dir=ctx.data_dir)
    try:
        ids = load_repo_pr_ids(conn=conn, repo=ctx.repo, pr_number=ctx.pr_number)
        rows = conn.execute(
            """
            select se.occurred_at as start_ts, ee.occurred_at as end_ts
            from pull_request_review_request_intervals rri
            join events se on se.id = rri.start_event_id
            left join events ee on ee.id = rri.end_event_id
            where rri.pull_request_id = ?
            """,
            (ids.pull_request_id,),
        ).fetchall()
    finally:
        conn.close()

    cutoff_s = cutoff_sql(ctx.cutoff)
    add_n = sum(1 for r in rows if r["start_ts"] is not None and str(r["start_ts"]) <= cutoff_s)
    remove_n = sum(1 for r in rows if r["end_ts"] is not None and str(r["end_ts"]) <= cutoff_s)
    return add_n, remove_n


def requested_overlap_with_codeowners(
    *,
    codeowner_logins: set[str],
    requested_user_logins: set[str],
) -> bool:
    owners = {x.lower() for x in codeowner_logins}
    requested = {x.lower() for x in requested_user_logins}
    return len(owners & requested) > 0


def mentions_overlap_with_requests(
    *,
    mentioned_logins: set[str],
    requested_user_logins: set[str],
) -> bool:
    mentions = {x.lower() for x in mentioned_logins}
    requested = {x.lower() for x in requested_user_logins}
    return len(mentions & requested) > 0


def title_has_wip_signal(input: PRInputBundle) -> bool:
    title = (input.title or "").strip().lower()
    return any(hint in title for hint in WIP_TITLE_HINTS)


def _requested_login_sets(input: PRInputBundle) -> tuple[set[str], set[str]]:
    users = {
        rr.reviewer
        for rr in input.review_requests
        if rr.reviewer_type.lower() == "user"
    }
    teams = {
        rr.reviewer
        for rr in input.review_requests
        if rr.reviewer_type.lower() == "team"
    }
    return users, teams


def _mentioned_user_logins(input: PRInputBundle) -> set[str]:
    text = "\n".join([input.title or "", input.body or ""])
    return {m.group("user") for m in _USER_MENTION_RE.finditer(text)}


def _comment_counts_human_bot(ctx: FeatureExtractionContext) -> tuple[int, int]:
    conn = connect_repo_db(repo=ctx.repo, data_dir=ctx.data_dir)
    try:
        ids = load_repo_pr_ids(conn=conn, repo=ctx.repo, pr_number=ctx.pr_number)
        try:
            rows = conn.execute(
                """
                select lower(coalesce(u.type, 'User')) as user_type, count(*) as n
                from comments c
                join users u on u.id = c.user_id
                where c.repo_id = ?
                  and c.pull_request_id = ?
                  and c.created_at <= ?
                group by lower(coalesce(u.type, 'User'))
                """,
                (ids.repo_id, ids.pull_request_id, cutoff_sql(ctx.cutoff)),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = conn.execute(
                """
                select 'user' as user_type, count(*) as n
                from comments c
                where c.repo_id = ?
                  and c.pull_request_id = ?
                  and c.created_at <= ?
                """,
                (ids.repo_id, ids.pull_request_id, cutoff_sql(ctx.cutoff)),
            ).fetchall()
    finally:
        conn.close()

    bot = 0
    human = 0
    for r in rows:
        t = str(r["user_type"]).lower()
        if t == "bot":
            bot += int(r["n"])
        else:
            human += int(r["n"])
    return human, bot


def build_pr_timeline_features(
    input: PRInputBundle,
    *,
    data_dir: str,
    codeowner_logins: set[str] | None = None,
) -> dict[str, Any]:
    ctx = FeatureExtractionContext(
        repo=input.repo,
        pr_number=input.pr_number,
        cutoff=input.cutoff,
        data_dir=data_dir,
    )

    req_users, req_teams = _requested_login_sets(input)
    mentioned = _mentioned_user_logins(input)

    review_states = review_state_counts_pre_cutoff(ctx)
    request_add_n, request_remove_n = request_event_add_remove_counts(ctx)
    human_comments, bot_comments = _comment_counts_human_bot(ctx)

    non_author_comments = non_author_comment_count_pre_cutoff(ctx)
    reviews_n = review_count_pre_cutoff(ctx)

    participants_non_author = max(0, unique_participants_count(ctx) - (1 if input.author_login else 0))
    actor_counts = Counter({"comments": non_author_comments, "reviews": reviews_n})
    total_actor_events = sum(actor_counts.values())
    if total_actor_events <= 0:
        attn_entropy = 0.0
    else:
        p1 = float(actor_counts["comments"]) / float(total_actor_events)
        p2 = float(actor_counts["reviews"]) / float(total_actor_events)
        import math

        h = 0.0
        for p in (p1, p2):
            if p > 0:
                h -= p * math.log(p)
        attn_entropy = h / math.log(2) if h > 0 else 0.0

    out: dict[str, Any] = {
        # B1 trajectory
        "pr.trajectory.age_seconds": pr_age_seconds_at_cutoff(input),
        "pr.trajectory.head_updates.count_1d": head_updates_in_window_count(ctx, days=1),
        "pr.trajectory.head_updates.count_7d": head_updates_in_window_count(ctx, days=7),
        "pr.trajectory.head_updates.count_30d": head_updates_in_window_count(ctx, days=30),
        "pr.trajectory.time_since_last_head_update_seconds": time_since_last_head_update_seconds(ctx),
        "pr.trajectory.head_update_burstiness": head_update_burstiness_last_6h(ctx),
        "pr.trajectory.comment_count.author": author_comment_count_pre_cutoff(ctx),
        # Geometry-lite trajectory (without historical per-head file-shape reconstruction)
        "pr.geometry.trajectory.head_updates.count_1d": head_updates_in_window_count(ctx, days=1),
        "pr.geometry.trajectory.head_updates.count_7d": head_updates_in_window_count(ctx, days=7),
        "pr.geometry.trajectory.time_since_last_head_update_seconds": time_since_last_head_update_seconds(ctx),
        "pr.geometry.trajectory.update_burstiness_6h": head_update_burstiness_last_6h(ctx),
        "pr.trajectory.comment_count.non_author": non_author_comments,
        "pr.trajectory.unique_participants_count": unique_participants_count(ctx),
        "pr.trajectory.review_count": reviews_n,
        "pr.trajectory.review_state_counts.approve": review_states["approve"],
        "pr.trajectory.review_state_counts.comment": review_states["comment"],
        "pr.trajectory.review_state_counts.changes_requested": review_states["changes_requested"],
        "pr.trajectory.request_events.add_count": request_add_n,
        "pr.trajectory.request_events.remove_count": request_remove_n,
        # B2 attention
        "pr.attention.has_any_non_author_comment": non_author_comments > 0,
        "pr.attention.has_any_review": reviews_n > 0,
        "pr.attention.non_author_participants_count": participants_non_author,
        "pr.attention.bot_comment_count": bot_comments,
        "pr.attention.human_comment_count": human_comments,
        "pr.attention.attention_entropy_by_actor": attn_entropy,
        # C3 request_overlap
        "pr.request_overlap.requested_users_count": len(req_users),
        "pr.request_overlap.requested_teams_count": len(req_teams),
        "pr.request_overlap.any_active_requests": len(req_users) + len(req_teams) > 0,
        "pr.request_overlap.overlap_with_codeowners.count": len({x.lower() for x in req_users} & {x.lower() for x in (codeowner_logins or set())}),
        "pr.request_overlap.overlap_with_codeowners.share": (
            float(len({x.lower() for x in req_users} & {x.lower() for x in (codeowner_logins or set())}))
            / float(len(req_users))
            if req_users
            else 0.0
        ),
        "pr.request_overlap.overlap_mentions_with_requests.count": len({x.lower() for x in mentioned} & {x.lower() for x in req_users}),
        # PR x silence/absence relations
        "pr.silence.no_non_author_attention_pre_cutoff": participants_non_author == 0,
        "pr.silence.no_owner_overlap_with_requests": len({x.lower() for x in req_users} & {x.lower() for x in (codeowner_logins or set())}) == 0,
        "pr.silence.no_active_review_requests": len(req_users) + len(req_teams) == 0,
        "pr.silence.no_recent_author_followup_24h": (
            author_comment_count_pre_cutoff(ctx) == 0
            and head_updates_in_window_count(ctx, days=1) == 0
        ),
        # carry meta signal here until draft state is wired into snapshot
        "pr.meta.is_draft": is_draft_at_cutoff(ctx),
    }

    # Compatibility aliases.
    out.update(
        {
            "pr.timeline.is_draft_at_cutoff": out["pr.meta.is_draft"],
            "pr.timeline.age_seconds": out["pr.trajectory.age_seconds"],
            "pr.timeline.seconds_since_last_head_update": out["pr.trajectory.time_since_last_head_update_seconds"],
            "pr.timeline.head_updates_pre_cutoff": head_updates_pre_cutoff_count(ctx),
            "pr.timeline.seconds_since_last_author_activity": last_author_activity_pre_cutoff_seconds(ctx),
            "pr.timeline.author_comments_pre_cutoff": out["pr.trajectory.comment_count.author"],
            "pr.timeline.non_author_comments_pre_cutoff": out["pr.trajectory.comment_count.non_author"],
            "pr.timeline.reviews_pre_cutoff": out["pr.trajectory.review_count"],
            "pr.timeline.any_active_review_requests": out["pr.request_overlap.any_active_requests"],
            "pr.timeline.requested_users_count": out["pr.request_overlap.requested_users_count"],
            "pr.timeline.requested_teams_count": out["pr.request_overlap.requested_teams_count"],
            "pr.timeline.reviewer_request_breadth": int(len(req_users) > 0) + int(len(req_teams) > 0),
            "pr.timeline.requested_overlap_codeowners": requested_overlap_with_codeowners(
                codeowner_logins=(codeowner_logins or set()),
                requested_user_logins=req_users,
            ),
            "pr.timeline.mentions_overlap_requests": mentions_overlap_with_requests(
                mentioned_logins=mentioned,
                requested_user_logins=req_users,
            ),
            "pr.timeline.title_has_wip_signal": title_has_wip_signal(input),
            "pr.timeline.requested_team_presence": len(req_teams) > 0,
        }
    )

    return {k: out[k] for k in sorted(out)}


def _seconds_between(later: datetime, earlier: datetime | None) -> float | None:
    if earlier is None:
        return None
    return max(0.0, (later - earlier).total_seconds())


_USER_MENTION_RE = re.compile(
    r"(?<![A-Za-z0-9_])@(?P<user>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))"
)
