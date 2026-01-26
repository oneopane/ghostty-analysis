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
from ..providers.github.auth import select_auth_token
from ..providers.github.client import GitHubRestClient
from ..intervals.rebuild import rebuild_intervals
from .qa import GapRecorder, write_qa_report
from ..storage.db import get_engine, get_session, init_db
from ..storage.upsert import (
    insert_event,
    upsert_comment,
    upsert_commit,
    upsert_issue,
    upsert_label,
    upsert_milestone,
    upsert_pull_request,
    upsert_ref,
    upsert_repo,
    upsert_release,
    upsert_review,
    upsert_team,
    upsert_user,
    upsert_watermark,
)
from ..utils.time import in_window, parse_datetime, resolve_window


async def backfill_repo(
    repo_full_name: str,
    db_path,
    *,
    client: GitHubRestClient | None = None,
    max_pages: int | None = None,
    start_at: str | None = None,
    end_at: str | None = None,
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
            await _run_backfill(
                session,
                client,
                owner,
                name,
                max_pages=max_pages,
                start_at=start_at,
                end_at=end_at,
            )
    else:
        await _run_backfill(
            session,
            client,
            owner,
            name,
            max_pages=max_pages,
            start_at=start_at,
            end_at=end_at,
        )


async def _run_backfill(
    session,
    client: GitHubRestClient,
    owner: str,
    name: str,
    *,
    max_pages: int | None,
    start_at: str | None,
    end_at: str | None,
) -> None:
    repo = await client.get_json(f"/repos/{owner}/{name}")
    upsert_user(session, repo.get("owner"))
    repo_id = upsert_repo(session, repo)
    session.commit()

    window_start, window_end = resolve_window(start_at, end_at)

    max_commit_time = None
    max_issue_updated = None
    max_pr_updated = None

    async for commit in client.paginate(
        f"/repos/{owner}/{name}/commits",
        params={"per_page": 100},
        on_gap=GapRecorder(session, repo_id, "commits"),
        resource="commits",
        max_pages=max_pages,
    ):
        committed_at = parse_datetime(
            (commit.get("commit") or {}).get("committer", {}).get("date")
        )
        if not in_window(committed_at, window_start, window_end):
            continue
        upsert_user(session, commit.get("author"))
        upsert_user(session, commit.get("committer"))
        upsert_commit(session, repo_id, commit)
        if committed_at and (max_commit_time is None or committed_at > max_commit_time):
            max_commit_time = committed_at
    session.commit()

    async for branch in client.paginate(
        f"/repos/{owner}/{name}/branches",
        params={"per_page": 100},
        on_gap=GapRecorder(session, repo_id, "branches"),
        resource="branches",
        max_pages=max_pages,
    ):
        upsert_ref(
            session,
            repo_id,
            ref_type="branch",
            name=branch.get("name"),
            sha=(branch.get("commit") or {}).get("sha"),
            is_protected=branch.get("protected"),
        )
    session.commit()

    async for tag in client.paginate(
        f"/repos/{owner}/{name}/tags",
        params={"per_page": 100},
        on_gap=GapRecorder(session, repo_id, "tags"),
        resource="tags",
        max_pages=max_pages,
    ):
        upsert_ref(
            session,
            repo_id,
            ref_type="tag",
            name=tag.get("name"),
            sha=(tag.get("commit") or {}).get("sha"),
            is_protected=None,
        )
    session.commit()

    async for release in client.paginate(
        f"/repos/{owner}/{name}/releases",
        params={"per_page": 100},
        on_gap=GapRecorder(session, repo_id, "releases"),
        resource="releases",
        max_pages=max_pages,
    ):
        release_time = release.get("published_at") or release.get("created_at")
        if not in_window(release_time, window_start, window_end):
            continue
        upsert_user(session, release.get("author"))
        upsert_release(session, repo_id, release)
    session.commit()

    pr_by_number: dict[int, dict] = {}
    pr_id_by_number: dict[int, int] = {}

    async for pr in client.paginate(
        f"/repos/{owner}/{name}/pulls",
        params={"state": "all", "per_page": 100},
        on_gap=GapRecorder(session, repo_id, "pulls"),
        resource="pulls",
        max_pages=max_pages,
    ):
        if not _include_object_in_window(pr, window_start, window_end):
            continue
        upsert_user(session, pr.get("user"))
        pr_by_number[pr.get("number")] = pr
        pr_id = upsert_pull_request(session, repo_id, pr, issue_id=None)
        pr_id_by_number[pr.get("number")] = pr_id
        _insert_events(
            session, normalize_pull_request(pr, repo_id), window_start, window_end
        )
        pr_updated = parse_datetime(pr.get("updated_at"))
        if pr_updated and (max_pr_updated is None or pr_updated > max_pr_updated):
            max_pr_updated = pr_updated
    session.commit()

    issues: list[dict] = []
    issue_id_by_number: dict[int, int] = {}
    async for issue in client.paginate(
        f"/repos/{owner}/{name}/issues",
        params={"state": "all", "per_page": 100},
        on_gap=GapRecorder(session, repo_id, "issues"),
        resource="issues",
        max_pages=max_pages,
    ):
        if not _include_object_in_window(issue, window_start, window_end):
            continue
        upsert_user(session, issue.get("user"))
        for label in issue.get("labels") or []:
            upsert_label(session, repo_id, label)
        if issue.get("milestone"):
            upsert_milestone(session, repo_id, issue.get("milestone"))
        issue_id = upsert_issue(session, repo_id, issue)
        issue_id_by_number[issue.get("number")] = issue_id
        issues.append(issue)
        _insert_events(
            session, normalize_issue_opened(issue, repo_id), window_start, window_end
        )
        _insert_events(
            session, normalize_issue_closed(issue, repo_id), window_start, window_end
        )
        issue_updated = parse_datetime(issue.get("updated_at"))
        if issue_updated and (
            max_issue_updated is None or issue_updated > max_issue_updated
        ):
            max_issue_updated = issue_updated
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
            on_gap=GapRecorder(session, repo_id, "issue_events"),
            resource="issue_events",
            max_pages=max_pages,
        ):
            _upsert_related_for_issue_event(session, repo_id, event_payload)
            _insert_events(
                session,
                normalize_issue_event(
                    issue_id=issue_id,
                    repo_id=repo_id,
                    payload=event_payload,
                    pull_request_id=pr_id,
                ),
                window_start,
                window_end,
            )

        async for comment in client.paginate(
            f"/repos/{owner}/{name}/issues/{number}/comments",
            params={"per_page": 100},
            on_gap=GapRecorder(session, repo_id, "issue_comments"),
            resource="issue_comments",
            max_pages=max_pages,
        ):
            if not _include_comment_in_window(comment, window_start, window_end):
                continue
            upsert_user(session, comment.get("user"))
            upsert_comment(
                session,
                repo_id,
                comment,
                issue_id=issue_id,
                pull_request_id=pr_id,
                comment_type="issue",
            )
            _insert_events(
                session,
                normalize_issue_comment(comment, repo_id, issue_id),
                window_start,
                window_end,
            )
    session.commit()

    for number, pr in pr_by_number.items():
        pr_id = pr_id_by_number.get(number)
        if pr_id is None:
            continue
        async for review in client.paginate(
            f"/repos/{owner}/{name}/pulls/{number}/reviews",
            params={"per_page": 100},
            on_gap=GapRecorder(session, repo_id, "reviews"),
            resource="reviews",
            max_pages=max_pages,
        ):
            if not in_window(review.get("submitted_at"), window_start, window_end):
                continue
            upsert_user(session, review.get("user"))
            upsert_review(session, repo_id, pr_id, review)
            _insert_events(
                session,
                normalize_review(review, repo_id, pr_id),
                window_start,
                window_end,
            )

        async for comment in client.paginate(
            f"/repos/{owner}/{name}/pulls/{number}/comments",
            params={"per_page": 100},
            on_gap=GapRecorder(session, repo_id, "review_comments"),
            resource="review_comments",
            max_pages=max_pages,
        ):
            if not _include_comment_in_window(comment, window_start, window_end):
                continue
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
            _insert_events(
                session,
                normalize_review_comment(comment, repo_id, pr_id, review_id),
                window_start,
                window_end,
            )
    session.commit()

    if max_commit_time:
        upsert_watermark(session, repo_id, "commits", updated_at=max_commit_time)
    if max_issue_updated:
        upsert_watermark(session, repo_id, "issues", updated_at=max_issue_updated)
    if max_pr_updated:
        upsert_watermark(session, repo_id, "pulls", updated_at=max_pr_updated)
    session.commit()

    rebuild_intervals(session, repo_id)
    write_qa_report(session, repo_id)


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


def _include_object_in_window(payload: dict, start_at, end_at) -> bool:
    created = payload.get("created_at")
    updated = payload.get("updated_at") or created
    if start_at and updated and parse_datetime(updated) < start_at:
        return False
    if end_at and created and parse_datetime(created) > end_at:
        return False
    return True


def _include_comment_in_window(comment: dict, start_at, end_at) -> bool:
    created = comment.get("created_at")
    updated = comment.get("updated_at") or created
    if start_at and updated and parse_datetime(updated) < start_at:
        return False
    if end_at and created and parse_datetime(created) > end_at:
        return False
    return True


def _insert_events(session, events, start_at, end_at) -> None:
    for event in events:
        if in_window(event.occurred_at, start_at, end_at):
            insert_event(session, event)
