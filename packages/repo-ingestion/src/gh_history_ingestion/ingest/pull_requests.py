from __future__ import annotations

from sqlalchemy import select

from ..events.normalize import (
    normalize_issue_closed,
    normalize_issue_opened,
    normalize_pull_request,
)
from ..github.auth import select_auth_token
from ..github.client import GitHubRestClient
from ..intervals.rebuild import rebuild_intervals
from ..storage.db import get_engine, get_session, init_db
from ..storage.schema import Issue
from ..storage.upsert import (
    insert_event,
    upsert_issue,
    upsert_label,
    upsert_milestone,
    upsert_pull_request,
    upsert_repo,
    upsert_user,
)
from ..utils.time import parse_datetime
from .qa import GapRecorder, write_qa_report
from .pull_request_files import ingest_pull_request_files


async def backfill_pull_requests(
    repo_full_name: str,
    db_path,
    *,
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

    rebuild_intervals(
        session,
        repo_id,
        issue_ids=list(issue_id_by_number.values()) or None,
        pr_ids=list(pr_id_by_number.values()) or None,
    )
    write_qa_report(session, repo_id)
