from __future__ import annotations

from ..events.normalize import (
    normalize_issue_closed,
    normalize_issue_comment,
    normalize_issue_event,
    normalize_issue_opened,
    normalize_pull_request,
    normalize_review,
    normalize_review_comment,
)
from ..github.auth import select_auth_token
from ..github.client import GitHubRestClient
from ..intervals.rebuild import rebuild_intervals
from ..storage.db import get_engine, get_session, init_db
from ..storage.upsert import (
    insert_event,
    upsert_comment,
    upsert_issue,
    upsert_label,
    upsert_milestone,
    upsert_pull_request,
    upsert_repo,
    upsert_review,
    upsert_team,
    upsert_user,
)


async def backfill_repo(
    repo_full_name: str,
    db_path,
    *,
    client: GitHubRestClient | None = None,
) -> None:
    owner, name = repo_full_name.split("/", 1)
    engine = get_engine(db_path)
    init_db(engine)
    session = get_session(engine)

    if client is None:
        token = select_auth_token()
        client = GitHubRestClient(token=token)

    if hasattr(client, "__aenter__"):
        async with client:
            await _run_backfill(session, client, owner, name)
    else:
        await _run_backfill(session, client, owner, name)


async def _run_backfill(session, client: GitHubRestClient, owner: str, name: str) -> None:
    repo = await client.get_json(f"/repos/{owner}/{name}")
    upsert_user(session, repo.get("owner"))
    repo_id = upsert_repo(session, repo)
    session.commit()

    pr_by_number: dict[int, dict] = {}
    pr_id_by_number: dict[int, int] = {}

    async for pr in client.paginate(
        f"/repos/{owner}/{name}/pulls",
        params={"state": "all", "per_page": 100},
    ):
        upsert_user(session, pr.get("user"))
        pr_by_number[pr.get("number")] = pr
        pr_id = upsert_pull_request(session, repo_id, pr, issue_id=None)
        pr_id_by_number[pr.get("number")] = pr_id
        for event in normalize_pull_request(pr, repo_id):
            insert_event(session, event)
    session.commit()

    issues: list[dict] = []
    issue_id_by_number: dict[int, int] = {}
    async for issue in client.paginate(
        f"/repos/{owner}/{name}/issues",
        params={"state": "all", "per_page": 100},
    ):
        upsert_user(session, issue.get("user"))
        issue_id = upsert_issue(session, repo_id, issue)
        issue_id_by_number[issue.get("number")] = issue_id
        issues.append(issue)
        for event in normalize_issue_opened(issue, repo_id):
            insert_event(session, event)
        for event in normalize_issue_closed(issue, repo_id):
            insert_event(session, event)
    session.commit()

    for number, pr in pr_by_number.items():
        issue_id = issue_id_by_number.get(number)
        if issue_id is not None:
            upsert_pull_request(session, repo_id, pr, issue_id=issue_id)
    session.commit()

    for issue in issues:
        number = issue.get("number")
        issue_id = issue_id_by_number[number]
        pr_id = pr_id_by_number.get(number)

        async for event_payload in client.paginate(
            f"/repos/{owner}/{name}/issues/{number}/events",
            params={"per_page": 100},
        ):
            _upsert_related_for_issue_event(session, repo_id, event_payload)
            for event in normalize_issue_event(
                issue_id=issue_id,
                repo_id=repo_id,
                payload=event_payload,
                pull_request_id=pr_id,
            ):
                insert_event(session, event)

        async for comment in client.paginate(
            f"/repos/{owner}/{name}/issues/{number}/comments",
            params={"per_page": 100},
        ):
            upsert_user(session, comment.get("user"))
            upsert_comment(
                session,
                repo_id,
                comment,
                issue_id=issue_id,
                pull_request_id=pr_id,
                comment_type="issue",
            )
            for event in normalize_issue_comment(comment, repo_id, issue_id):
                insert_event(session, event)
    session.commit()

    for number, pr in pr_by_number.items():
        pr_id = pr_id_by_number.get(number)
        if pr_id is None:
            continue
        async for review in client.paginate(
            f"/repos/{owner}/{name}/pulls/{number}/reviews",
            params={"per_page": 100},
        ):
            upsert_user(session, review.get("user"))
            upsert_review(session, repo_id, pr_id, review)
            for event in normalize_review(review, repo_id, pr_id):
                insert_event(session, event)

        async for comment in client.paginate(
            f"/repos/{owner}/{name}/pulls/{number}/comments",
            params={"per_page": 100},
        ):
            upsert_user(session, comment.get("user"))
            review_id = comment.get("pull_request_review_id")
            upsert_comment(
                session,
                repo_id,
                comment,
                pull_request_id=pr_id,
                review_id=review_id,
                comment_type="review",
            )
            for event in normalize_review_comment(
                comment, repo_id, pr_id, review_id
            ):
                insert_event(session, event)
    session.commit()

    rebuild_intervals(session, repo_id)


def _upsert_related_for_issue_event(session, repo_id: int, payload: dict) -> None:
    if payload.get("label"):
        upsert_label(session, repo_id, payload.get("label"))
    if payload.get("assignee"):
        upsert_user(session, payload.get("assignee"))
    if payload.get("milestone"):
        upsert_milestone(session, repo_id, payload.get("milestone"))
    if payload.get("requested_reviewer"):
        upsert_user(session, payload.get("requested_reviewer"))
    if payload.get("requested_team"):
        upsert_team(session, payload.get("requested_team"))
