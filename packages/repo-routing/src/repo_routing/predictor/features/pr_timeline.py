from __future__ import annotations

import re
from datetime import datetime

from ...inputs.models import PRInputBundle
from .patterns import WIP_TITLE_HINTS
from .schemas import FeatureExtractionContext
from .sql import (
    active_review_request_counts,
    comment_counts_pre_cutoff,
    connect_repo_db,
    count_head_updates_pre_cutoff,
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


def reviewer_request_breadth(ctx: FeatureExtractionContext) -> int:
    users_n = requested_users_count_at_cutoff(ctx)
    teams_n = requested_teams_count_at_cutoff(ctx)
    breadth = 0
    if users_n > 0:
        breadth += 1
    if teams_n > 0:
        breadth += 1
    return breadth


def requested_overlap_with_codeowners(
    ctx: FeatureExtractionContext,
    *,
    codeowner_logins: set[str],
    requested_user_logins: set[str],
) -> bool:
    del ctx
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


def build_pr_timeline_features(
    input: PRInputBundle,
    *,
    data_dir: str,
    codeowner_logins: set[str] | None = None,
) -> dict[str, int | float | bool | None]:
    ctx = FeatureExtractionContext(
        repo=input.repo,
        pr_number=input.pr_number,
        cutoff=input.cutoff,
        data_dir=data_dir,
    )

    req_users, req_teams = _requested_login_sets(input)
    mentioned = _mentioned_user_logins(input)

    return {
        "pr.timeline.is_draft_at_cutoff": is_draft_at_cutoff(ctx),
        "pr.timeline.age_seconds": pr_age_seconds_at_cutoff(input),
        "pr.timeline.seconds_since_last_head_update": time_since_last_head_update_seconds(ctx),
        "pr.timeline.head_updates_pre_cutoff": head_updates_pre_cutoff_count(ctx),
        "pr.timeline.seconds_since_last_author_activity": last_author_activity_pre_cutoff_seconds(ctx),
        "pr.timeline.author_comments_pre_cutoff": author_comment_count_pre_cutoff(ctx),
        "pr.timeline.non_author_comments_pre_cutoff": non_author_comment_count_pre_cutoff(ctx),
        "pr.timeline.reviews_pre_cutoff": review_count_pre_cutoff(ctx),
        "pr.timeline.any_active_review_requests": any_active_review_requests_at_cutoff(ctx),
        "pr.timeline.requested_users_count": requested_users_count_at_cutoff(ctx),
        "pr.timeline.requested_teams_count": requested_teams_count_at_cutoff(ctx),
        "pr.timeline.reviewer_request_breadth": reviewer_request_breadth(ctx),
        "pr.timeline.requested_overlap_codeowners": requested_overlap_with_codeowners(
            ctx,
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


def _seconds_between(later: datetime, earlier: datetime | None) -> float | None:
    if earlier is None:
        return None
    return max(0.0, (later - earlier).total_seconds())


_USER_MENTION_RE = re.compile(
    r"(?<![A-Za-z0-9_])@(?P<user>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))"
)
