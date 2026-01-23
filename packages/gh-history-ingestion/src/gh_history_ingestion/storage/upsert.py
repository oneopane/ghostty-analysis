from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy.dialects.sqlite import insert

from ..events.normalize import EventRecord
from ..utils.time import parse_datetime
from .schema import (
    Comment,
    Event,
    Issue,
    Label,
    Milestone,
    PullRequest,
    Repo,
    Review,
    Team,
    User,
)


def _upsert(session, model, values, index_elements):
    stmt = insert(model).values(**values)
    update = {k: v for k, v in values.items() if k not in index_elements}
    stmt = stmt.on_conflict_do_update(index_elements=index_elements, set_=update)
    session.execute(stmt)


def upsert_user(session, user: dict | None) -> int | None:
    if not user:
        return None
    values = {
        "id": user.get("id"),
        "login": user.get("login"),
        "type": user.get("type"),
        "site_admin": user.get("site_admin"),
        "avatar_url": user.get("avatar_url"),
    }
    _upsert(session, User, values, ["id"])
    return values["id"]


def upsert_team(session, team: dict | None) -> int | None:
    if not team:
        return None
    values = {
        "id": team.get("id"),
        "slug": team.get("slug"),
        "name": team.get("name"),
    }
    _upsert(session, Team, values, ["id"])
    return values["id"]


def upsert_repo(session, repo: dict) -> int:
    owner = repo.get("owner") or {}
    values = {
        "id": repo.get("id"),
        "owner_id": owner.get("id"),
        "owner_login": owner.get("login") or repo.get("owner", {}).get("login", ""),
        "name": repo.get("name"),
        "full_name": repo.get("full_name"),
        "is_private": repo.get("private"),
        "description": repo.get("description"),
        "default_branch": repo.get("default_branch"),
        "created_at": parse_datetime(repo.get("created_at")),
        "updated_at": parse_datetime(repo.get("updated_at")),
        "pushed_at": parse_datetime(repo.get("pushed_at")),
        "archived": repo.get("archived"),
        "disabled": repo.get("disabled"),
    }
    _upsert(session, Repo, values, ["id"])
    return values["id"]


def upsert_label(session, repo_id: int, label: dict | None) -> int | None:
    if not label:
        return None
    values = {
        "id": label.get("id"),
        "repo_id": repo_id,
        "name": label.get("name"),
        "color": label.get("color"),
        "description": label.get("description"),
        "is_default": label.get("default"),
    }
    _upsert(session, Label, values, ["id"])
    return values["id"]


def upsert_milestone(session, repo_id: int, milestone: dict | None) -> int | None:
    if not milestone:
        return None
    values = {
        "id": milestone.get("id"),
        "repo_id": repo_id,
        "number": milestone.get("number"),
        "title": milestone.get("title"),
        "state": milestone.get("state"),
        "description": milestone.get("description"),
        "due_on": parse_datetime(milestone.get("due_on")),
        "closed_at": parse_datetime(milestone.get("closed_at")),
        "created_at": parse_datetime(milestone.get("created_at")),
        "updated_at": parse_datetime(milestone.get("updated_at")),
    }
    _upsert(session, Milestone, values, ["id"])
    return values["id"]


def upsert_issue(session, repo_id: int, issue: dict) -> int:
    values = {
        "id": issue.get("id"),
        "repo_id": repo_id,
        "number": issue.get("number"),
        "user_id": issue.get("user", {}).get("id"),
        "title": issue.get("title"),
        "body": issue.get("body"),
        "state": issue.get("state"),
        "created_at": parse_datetime(issue.get("created_at")),
        "updated_at": parse_datetime(issue.get("updated_at")),
        "closed_at": parse_datetime(issue.get("closed_at")),
        "is_pull_request": bool(issue.get("pull_request")),
        "locked": issue.get("locked"),
    }
    _upsert(session, Issue, values, ["id"])
    return values["id"]


def upsert_pull_request(session, repo_id: int, pr: dict, issue_id: int | None) -> int:
    values = {
        "id": pr.get("id"),
        "repo_id": repo_id,
        "number": pr.get("number"),
        "issue_id": issue_id,
        "user_id": pr.get("user", {}).get("id"),
        "title": pr.get("title"),
        "body": pr.get("body"),
        "state": pr.get("state"),
        "draft": pr.get("draft"),
        "merged": pr.get("merged"),
        "merge_commit_sha": pr.get("merge_commit_sha"),
        "head_sha": pr.get("head", {}).get("sha"),
        "head_ref": pr.get("head", {}).get("ref"),
        "base_sha": pr.get("base", {}).get("sha"),
        "base_ref": pr.get("base", {}).get("ref"),
        "created_at": parse_datetime(pr.get("created_at")),
        "updated_at": parse_datetime(pr.get("updated_at")),
        "closed_at": parse_datetime(pr.get("closed_at")),
        "merged_at": parse_datetime(pr.get("merged_at")),
    }
    _upsert(session, PullRequest, values, ["id"])
    return values["id"]


def upsert_review(session, repo_id: int, pr_id: int, review: dict) -> int:
    values = {
        "id": review.get("id"),
        "repo_id": repo_id,
        "pull_request_id": pr_id,
        "user_id": review.get("user", {}).get("id"),
        "state": review.get("state"),
        "body": review.get("body"),
        "submitted_at": parse_datetime(review.get("submitted_at")),
        "commit_id": review.get("commit_id"),
    }
    _upsert(session, Review, values, ["id"])
    return values["id"]


def upsert_comment(
    session,
    repo_id: int,
    comment: dict,
    *,
    issue_id: int | None = None,
    pull_request_id: int | None = None,
    review_id: int | None = None,
    comment_type: str | None = None,
) -> int:
    values = {
        "id": comment.get("id"),
        "repo_id": repo_id,
        "issue_id": issue_id,
        "pull_request_id": pull_request_id,
        "review_id": review_id,
        "user_id": comment.get("user", {}).get("id"),
        "body": comment.get("body"),
        "created_at": parse_datetime(comment.get("created_at")),
        "updated_at": parse_datetime(comment.get("updated_at")),
        "path": comment.get("path"),
        "position": comment.get("position"),
        "commit_id": comment.get("commit_id"),
        "in_reply_to_id": comment.get("in_reply_to_id"),
        "comment_type": comment_type,
    }
    _upsert(session, Comment, values, ["id"])
    return values["id"]


def insert_event(session, event: EventRecord) -> None:
    occurred_at = parse_datetime(event.occurred_at)
    event_key = _event_key(event, occurred_at)
    values = {
        "repo_id": event.repo_id,
        "occurred_at": occurred_at,
        "actor_id": event.actor_id,
        "subject_type": event.subject_type,
        "subject_id": event.subject_id,
        "event_type": event.event_type,
        "object_type": event.object_type,
        "object_id": event.object_id,
        "commit_sha": event.commit_sha,
        "payload_json": json.dumps(event.payload) if event.payload is not None else None,
        "event_key": event_key,
    }
    stmt = insert(Event).values(**values)
    stmt = stmt.on_conflict_do_nothing(index_elements=["event_key"])
    session.execute(stmt)


def _event_key(event: EventRecord, occurred_at: datetime) -> str:
    return "|".join(
        [
            event.event_type,
            event.subject_type,
            str(event.subject_id),
            occurred_at.replace(tzinfo=timezone.utc).isoformat(),
            event.object_type or "",
            str(event.object_id or ""),
            event.commit_sha or "",
        ]
    )
