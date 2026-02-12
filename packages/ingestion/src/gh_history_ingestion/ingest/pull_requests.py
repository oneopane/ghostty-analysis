from __future__ import annotations

from sqlalchemy import select

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
from ..storage.schema import Issue
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
from ..utils.time import parse_datetime
from .qa import GapRecorder, write_qa_report
from .pull_request_files import ingest_pull_request_files


async def backfill_pull_requests(
    repo_full_name: str,
    db_path,
    *,
    with_truth: bool = False,
    start_at: str | None,
    end_at: str | None,
    client: GitHubRestClient | None = None,
    max_pages: int | None = None,
) -> None:
    """Backfill pull requests created in a time window.

    This is optimized for PR imports: it avoids fetching commits/refs/releases.
    """

    owner, name = repo_full_name.split("/", 1)
    engine = get_engine(db_path)
    init_db(engine)
    session = get_session(engine)

    if client is None:
        token = select_auth_token()
        client = GitHubRestClient(token=token)

    if hasattr(client, "__aenter__"):
        async with client:
            await _run_pr_backfill(
                session,
                client,
                owner,
                name,
                with_truth=with_truth,
                start_at=start_at,
                end_at=end_at,
                max_pages=max_pages,
            )
    else:
        await _run_pr_backfill(
            session,
            client,
            owner,
            name,
            with_truth=with_truth,
            start_at=start_at,
            end_at=end_at,
            max_pages=max_pages,
        )


async def _run_pr_backfill(
    session,
    client: GitHubRestClient,
    owner: str,
    name: str,
    *,
    with_truth: bool,
    start_at: str | None,
    end_at: str | None,
    max_pages: int | None,
) -> None:
    repo = await client.get_json(f"/repos/{owner}/{name}")
    upsert_user(session, repo.get("owner"))
    repo_id = upsert_repo(session, repo)
    session.commit()

    window_start = parse_datetime(start_at) if start_at else None
    window_end = parse_datetime(end_at) if end_at else None

    pr_by_number: dict[int, dict] = {}
    pr_id_by_number: dict[int, int] = {}
    pr_numbers: set[int] = set()

    async for pr in client.paginate(
        f"/repos/{owner}/{name}/pulls",
        params={
            "state": "all",
            "per_page": 100,
            "sort": "created",
            "direction": "desc",
        },
        on_gap=GapRecorder(session, repo_id, "pulls"),
        resource="pulls",
        max_pages=max_pages,
    ):
        created_at = parse_datetime(pr.get("created_at"))
        if window_end and created_at and created_at > window_end:
            continue
        if window_start and created_at and created_at < window_start:
            break
        upsert_user(session, pr.get("user"))
        pr_by_number[pr.get("number")] = pr
        pr_numbers.add(pr.get("number"))
        pr_id = upsert_pull_request(session, repo_id, pr, issue_id=None)
        pr_id_by_number[pr.get("number")] = pr_id
        await ingest_pull_request_files(
            session,
            client,
            owner,
            name,
            repo_id=repo_id,
            pull_request_number=pr.get("number"),
            pull_request_id=pr_id,
            head_sha=(pr.get("head") or {}).get("sha"),
            max_pages=max_pages,
        )
        for event in normalize_pull_request(pr, repo_id):
            insert_event(session, event)
    session.commit()

    # Ensure the matching issue row exists for each PR (GitHub models PRs as issues too).
    issue_id_by_number: dict[int, int] = {}
    existing_issue_map = {
        number: issue_id
        for number, issue_id in session.execute(
            select(Issue.number, Issue.id).where(Issue.repo_id == repo_id)
        ).all()
    }
    for number, issue_id in existing_issue_map.items():
        if number in pr_numbers:
            issue_id_by_number[number] = issue_id

    # Fetch issues in bulk (much faster than one request per PR).
    async for issue in client.paginate(
        f"/repos/{owner}/{name}/issues",
        params={
            "state": "all",
            "per_page": 100,
            "sort": "created",
            "direction": "desc",
        },
        on_gap=GapRecorder(session, repo_id, "issues"),
        resource="issues",
        max_pages=max_pages,
    ):
        created_at = parse_datetime(issue.get("created_at"))
        if window_end and created_at and created_at > window_end:
            continue
        if window_start and created_at and created_at < window_start:
            break
        if not issue.get("pull_request"):
            continue
        number = issue.get("number")
        if number not in pr_numbers:
            continue
        if number in issue_id_by_number:
            continue
        upsert_user(session, issue.get("user"))
        for label in issue.get("labels") or []:
            upsert_label(session, repo_id, label)
        if issue.get("milestone"):
            upsert_milestone(session, repo_id, issue.get("milestone"))
        issue_id = upsert_issue(session, repo_id, issue)
        issue_id_by_number[number] = issue_id
        for event in normalize_issue_opened(issue, repo_id):
            insert_event(session, event)
        for event in normalize_issue_closed(issue, repo_id):
            insert_event(session, event)
    session.commit()

    for number, pr in pr_by_number.items():
        issue_id = issue_id_by_number.get(number)
        pr_id = pr_id_by_number.get(number)
        if pr_id is None:
            continue
        upsert_pull_request(session, repo_id, pr, issue_id=issue_id)
    session.commit()

    if with_truth:
        for number in sorted(pr_numbers):
            issue_id = issue_id_by_number.get(number)
            pr_id = pr_id_by_number.get(number)
            if pr_id is None or issue_id is None:
                continue
            await _ingest_pr_truth(
                session,
                client,
                owner,
                name,
                repo_id=repo_id,
                issue_id=issue_id,
                pull_request_id=pr_id,
                pull_request_number=number,
                max_pages=max_pages,
            )
        session.commit()

    rebuild_intervals(
        session,
        repo_id,
        issue_ids=list(issue_id_by_number.values()) or None,
        pr_ids=list(pr_id_by_number.values()) or None,
    )
    write_qa_report(session, repo_id)


async def _ingest_pr_truth(
    session,
    client: GitHubRestClient,
    owner: str,
    name: str,
    *,
    repo_id: int,
    issue_id: int,
    pull_request_id: int,
    pull_request_number: int,
    max_pages: int | None,
) -> None:
    async for event_payload in client.paginate(
        f"/repos/{owner}/{name}/issues/{pull_request_number}/events",
        params={"per_page": 100},
        on_gap=GapRecorder(session, repo_id, "issue_events"),
        resource="issue_events",
        max_pages=max_pages,
    ):
        _upsert_related_for_issue_event(session, repo_id, event_payload)
        for event in normalize_issue_event(
            issue_id=issue_id,
            repo_id=repo_id,
            payload=event_payload,
            pull_request_id=pull_request_id,
        ):
            insert_event(session, event)

    async for comment in client.paginate(
        f"/repos/{owner}/{name}/issues/{pull_request_number}/comments",
        params={"per_page": 100},
        on_gap=GapRecorder(session, repo_id, "issue_comments"),
        resource="issue_comments",
        max_pages=max_pages,
    ):
        upsert_user(session, comment.get("user"))
        upsert_comment(
            session,
            repo_id,
            comment,
            issue_id=issue_id,
            pull_request_id=pull_request_id,
            comment_type="issue",
        )
        for event in normalize_issue_comment(comment, repo_id, issue_id):
            insert_event(session, event)

    async for review in client.paginate(
        f"/repos/{owner}/{name}/pulls/{pull_request_number}/reviews",
        params={"per_page": 100},
        on_gap=GapRecorder(session, repo_id, "reviews"),
        resource="reviews",
        max_pages=max_pages,
    ):
        upsert_user(session, review.get("user"))
        upsert_review(session, repo_id, pull_request_id, review)
        for event in normalize_review(review, repo_id, pull_request_id):
            insert_event(session, event)

    async for comment in client.paginate(
        f"/repos/{owner}/{name}/pulls/{pull_request_number}/comments",
        params={"per_page": 100},
        on_gap=GapRecorder(session, repo_id, "review_comments"),
        resource="review_comments",
        max_pages=max_pages,
    ):
        upsert_user(session, comment.get("user"))
        review_id = comment.get("pull_request_review_id")
        upsert_comment(
            session,
            repo_id,
            comment,
            pull_request_id=pull_request_id,
            review_id=review_id,
            comment_type="review",
        )
        for event in normalize_review_comment(
            comment, repo_id, pull_request_id, review_id
        ):
            insert_event(session, event)


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
