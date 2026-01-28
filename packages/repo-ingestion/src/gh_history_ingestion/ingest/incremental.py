from __future__ import annotations

from datetime import datetime

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
from ..storage.schema import Issue, PullRequest
from ..storage.upsert import (
    get_watermark,
    insert_event,
    upsert_comment,
    upsert_commit,
    upsert_issue,
    upsert_label,
    upsert_milestone,
    upsert_pull_request,
    upsert_ref,
    upsert_release,
    upsert_repo,
    upsert_review,
    upsert_team,
    upsert_user,
    upsert_watermark,
)
from ..utils.time import parse_datetime
from .qa import GapRecorder, write_qa_report
from .pull_request_files import ingest_pull_request_files


async def incremental_update(
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
            await _run_incremental(session, client, owner, name)
    else:
        await _run_incremental(session, client, owner, name)


async def _run_incremental(
    session, client: GitHubRestClient, owner: str, name: str
) -> None:
    repo = await client.get_json(f"/repos/{owner}/{name}")
    upsert_user(session, repo.get("owner"))
    repo_id = upsert_repo(session, repo)
    session.commit()

    updated_issue_ids: list[int] = []
    updated_pr_ids: list[int] = []

    await _incremental_commits(session, client, owner, name, repo_id)
    await _incremental_refs_and_releases(session, client, owner, name, repo_id)
    updated_issue_ids = await _incremental_issues(session, client, owner, name, repo_id)
    updated_pr_ids = await _incremental_pull_requests(
        session, client, owner, name, repo_id
    )

    await _incremental_issue_activity(
        session, client, owner, name, repo_id, updated_issue_ids
    )
    await _incremental_pr_activity(
        session, client, owner, name, repo_id, updated_pr_ids
    )

    rebuild_intervals(
        session,
        repo_id,
        issue_ids=updated_issue_ids or None,
        pr_ids=updated_pr_ids or None,
    )
    write_qa_report(session, repo_id)


async def _incremental_commits(
    session, client: GitHubRestClient, owner: str, name: str, repo_id: int
) -> None:
    watermark = get_watermark(session, repo_id, "commits")
    params = {"per_page": 100}
    if watermark and watermark.updated_at:
        params["since"] = _format_since(watermark.updated_at)
    headers = _conditional_headers(watermark)
    latest_headers: dict[str, str] = {}
    max_seen: datetime | None = (
        parse_datetime(watermark.updated_at)
        if watermark and watermark.updated_at
        else None
    )

    async for commit in client.paginate_conditional(
        f"/repos/{owner}/{name}/commits",
        params=params,
        headers=headers,
        on_gap=GapRecorder(session, repo_id, "commits"),
        on_response=lambda resp: latest_headers.update(resp.headers),
        resource="commits",
    ):
        upsert_user(session, commit.get("author"))
        upsert_user(session, commit.get("committer"))
        upsert_commit(session, repo_id, commit)
        committed_at = parse_datetime(
            (commit.get("commit") or {}).get("committer", {}).get("date")
        )
        if committed_at and (max_seen is None or committed_at > max_seen):
            max_seen = committed_at
    session.commit()

    _update_watermark(session, repo_id, "commits", watermark, max_seen, latest_headers)
    session.commit()


async def _incremental_refs_and_releases(
    session, client: GitHubRestClient, owner: str, name: str, repo_id: int
) -> None:
    async for branch in client.paginate(
        f"/repos/{owner}/{name}/branches",
        params={"per_page": 100},
        on_gap=GapRecorder(session, repo_id, "branches"),
        resource="branches",
    ):
        upsert_ref(
            session,
            repo_id,
            ref_type="branch",
            name=branch.get("name"),
            sha=(branch.get("commit") or {}).get("sha"),
            is_protected=branch.get("protected"),
        )
    async for tag in client.paginate(
        f"/repos/{owner}/{name}/tags",
        params={"per_page": 100},
        on_gap=GapRecorder(session, repo_id, "tags"),
        resource="tags",
    ):
        upsert_ref(
            session,
            repo_id,
            ref_type="tag",
            name=tag.get("name"),
            sha=(tag.get("commit") or {}).get("sha"),
            is_protected=None,
        )
    async for release in client.paginate(
        f"/repos/{owner}/{name}/releases",
        params={"per_page": 100},
        on_gap=GapRecorder(session, repo_id, "releases"),
        resource="releases",
    ):
        upsert_user(session, release.get("author"))
        upsert_release(session, repo_id, release)
    session.commit()


async def _incremental_issues(
    session, client: GitHubRestClient, owner: str, name: str, repo_id: int
) -> list[int]:
    watermark = get_watermark(session, repo_id, "issues")
    params = {"state": "all", "per_page": 100}
    if watermark and watermark.updated_at:
        params["since"] = _format_since(watermark.updated_at)
    headers = _conditional_headers(watermark)
    latest_headers: dict[str, str] = {}
    max_seen: datetime | None = (
        parse_datetime(watermark.updated_at)
        if watermark and watermark.updated_at
        else None
    )
    updated_issue_ids: list[int] = []

    async for issue in client.paginate_conditional(
        f"/repos/{owner}/{name}/issues",
        params=params,
        headers=headers,
        on_gap=GapRecorder(session, repo_id, "issues"),
        on_response=lambda resp: latest_headers.update(resp.headers),
        resource="issues",
    ):
        upsert_user(session, issue.get("user"))
        for label in issue.get("labels") or []:
            upsert_label(session, repo_id, label)
        if issue.get("milestone"):
            upsert_milestone(session, repo_id, issue.get("milestone"))
        issue_id = upsert_issue(session, repo_id, issue)
        updated_issue_ids.append(issue_id)
        for event in normalize_issue_opened(issue, repo_id):
            insert_event(session, event)
        for event in normalize_issue_closed(issue, repo_id):
            insert_event(session, event)
        updated_at = parse_datetime(issue.get("updated_at"))
        if updated_at and (max_seen is None or updated_at > max_seen):
            max_seen = updated_at

    session.commit()
    _update_watermark(session, repo_id, "issues", watermark, max_seen, latest_headers)
    session.commit()
    return updated_issue_ids


async def _incremental_pull_requests(
    session, client: GitHubRestClient, owner: str, name: str, repo_id: int
) -> list[int]:
    watermark = get_watermark(session, repo_id, "pulls")
    params = {"state": "all", "per_page": 100, "sort": "updated", "direction": "desc"}
    headers = _conditional_headers(watermark)
    latest_headers: dict[str, str] = {}
    max_seen: datetime | None = (
        parse_datetime(watermark.updated_at)
        if watermark and watermark.updated_at
        else None
    )
    updated_pr_ids: list[int] = []
    issue_map = {
        number: issue_id
        for number, issue_id in session.execute(
            select(Issue.number, Issue.id).where(Issue.repo_id == repo_id)
        ).all()
    }

    async for pr in client.paginate_conditional(
        f"/repos/{owner}/{name}/pulls",
        params=params,
        headers=headers,
        on_gap=GapRecorder(session, repo_id, "pulls"),
        on_response=lambda resp: latest_headers.update(resp.headers),
        resource="pulls",
    ):
        updated_at = parse_datetime(pr.get("updated_at"))
        watermark_updated = (
            parse_datetime(watermark.updated_at)
            if watermark and watermark.updated_at
            else None
        )
        if watermark_updated and updated_at and updated_at <= watermark_updated:
            break
        upsert_user(session, pr.get("user"))
        issue_id = issue_map.get(pr.get("number"))
        pr_id = upsert_pull_request(session, repo_id, pr, issue_id=issue_id)
        updated_pr_ids.append(pr_id)
        await ingest_pull_request_files(
            session,
            client,
            owner,
            name,
            repo_id=repo_id,
            pull_request_number=pr.get("number"),
            pull_request_id=pr_id,
            head_sha=(pr.get("head") or {}).get("sha"),
        )
        for event in normalize_pull_request(pr, repo_id):
            insert_event(session, event)
        if updated_at and (max_seen is None or updated_at > max_seen):
            max_seen = updated_at

    session.commit()
    _update_watermark(session, repo_id, "pulls", watermark, max_seen, latest_headers)
    session.commit()
    return updated_pr_ids


async def _incremental_issue_activity(
    session,
    client: GitHubRestClient,
    owner: str,
    name: str,
    repo_id: int,
    issue_ids: list[int],
) -> None:
    if not issue_ids:
        return
    issue_numbers = {
        number
        for number, issue_id in session.execute(
            select(Issue.number, Issue.id).where(Issue.id.in_(issue_ids))
        ).all()
    }
    issue_id_by_number = {
        number: issue_id
        for number, issue_id in session.execute(
            select(Issue.number, Issue.id).where(Issue.id.in_(issue_ids))
        ).all()
    }
    pr_id_by_number = {
        number: pr_id
        for number, pr_id in session.execute(
            select(PullRequest.number, PullRequest.id).where(
                PullRequest.repo_id == repo_id
            )
        ).all()
    }

    for number in issue_numbers:
        issue_id = issue_id_by_number[number]
        pr_id = pr_id_by_number.get(number)
        async for event_payload in client.paginate(
            f"/repos/{owner}/{name}/issues/{number}/events",
            params={"per_page": 100},
            on_gap=GapRecorder(session, repo_id, "issue_events"),
            resource="issue_events",
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
            on_gap=GapRecorder(session, repo_id, "issue_comments"),
            resource="issue_comments",
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


async def _incremental_pr_activity(
    session,
    client: GitHubRestClient,
    owner: str,
    name: str,
    repo_id: int,
    pr_ids: list[int],
) -> None:
    if not pr_ids:
        return
    pr_rows = session.execute(
        select(PullRequest.number, PullRequest.id).where(PullRequest.id.in_(pr_ids))
    ).all()
    pr_numbers = {number for number, _ in pr_rows}
    pr_id_by_number = {number: pr_id for number, pr_id in pr_rows}

    for number in pr_numbers:
        pr_id = pr_id_by_number[number]
        async for review in client.paginate(
            f"/repos/{owner}/{name}/pulls/{number}/reviews",
            params={"per_page": 100},
            on_gap=GapRecorder(session, repo_id, "reviews"),
            resource="reviews",
        ):
            upsert_user(session, review.get("user"))
            upsert_review(session, repo_id, pr_id, review)
            for event in normalize_review(review, repo_id, pr_id):
                insert_event(session, event)

        async for comment in client.paginate(
            f"/repos/{owner}/{name}/pulls/{number}/comments",
            params={"per_page": 100},
            on_gap=GapRecorder(session, repo_id, "review_comments"),
            resource="review_comments",
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
            for event in normalize_review_comment(comment, repo_id, pr_id, review_id):
                insert_event(session, event)
    session.commit()


def _conditional_headers(watermark) -> dict | None:
    if watermark is None:
        return None
    if watermark.etag:
        return {"If-None-Match": watermark.etag}
    if watermark.last_modified:
        return {"If-Modified-Since": watermark.last_modified}
    return None


def _update_watermark(
    session,
    repo_id: int,
    resource: str,
    watermark,
    max_seen: datetime | None,
    latest_headers: dict[str, str],
) -> None:
    etag = _header_value(latest_headers, "ETag") or (
        watermark.etag if watermark else None
    )
    last_modified = _header_value(latest_headers, "Last-Modified") or (
        watermark.last_modified if watermark else None
    )
    updated_at = max_seen or (watermark.updated_at if watermark else None)
    updated_at = parse_datetime(updated_at) if updated_at else None
    upsert_watermark(
        session,
        repo_id,
        resource,
        updated_at=updated_at,
        etag=etag,
        last_modified=last_modified,
    )


def _header_value(headers: dict[str, str], key: str) -> str | None:
    if key in headers:
        return headers[key]
    lower = key.lower()
    for k, v in headers.items():
        if k.lower() == lower:
            return v
    return None


def _format_since(value: datetime) -> str:
    dt = parse_datetime(value)
    text = dt.isoformat()
    if text.endswith("+00:00"):
        return text.replace("+00:00", "Z")
    return text


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
