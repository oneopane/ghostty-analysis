from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..utils.time import parse_datetime


@dataclass(frozen=True)
class EventRecord:
    repo_id: int
    occurred_at: Any
    actor_id: int | None
    subject_type: str
    subject_id: int
    event_type: str
    object_type: str | None = None
    object_id: int | None = None
    commit_sha: str | None = None
    payload: dict | None = None


def normalize_issue_opened(issue: dict, repo_id: int) -> list[EventRecord]:
    actor_id = (issue.get("user") or {}).get("id")
    issue_id = issue.get("id")
    occurred_at = issue.get("created_at")
    return [
        EventRecord(
            repo_id=repo_id,
            occurred_at=occurred_at,
            actor_id=actor_id,
            subject_type="issue",
            subject_id=issue_id,
            event_type="issue.opened",
        ),
        EventRecord(
            repo_id=repo_id,
            occurred_at=occurred_at,
            actor_id=actor_id,
            subject_type="issue",
            subject_id=issue_id,
            event_type="issue.content.set",
            payload={"title": issue.get("title"), "body": issue.get("body")},
        ),
    ]


def normalize_issue_closed(issue: dict, repo_id: int) -> list[EventRecord]:
    if not issue.get("closed_at"):
        return []
    actor_id = (issue.get("user") or {}).get("id")
    return [
        EventRecord(
            repo_id=repo_id,
            occurred_at=issue.get("closed_at"),
            actor_id=actor_id,
            subject_type="issue",
            subject_id=issue.get("id"),
            event_type="issue.closed",
        )
    ]


def normalize_pull_request(pr: dict, repo_id: int) -> list[EventRecord]:
    actor_id = (pr.get("user") or {}).get("id")
    pr_id = pr.get("id")
    events = [
        EventRecord(
            repo_id=repo_id,
            occurred_at=pr.get("created_at"),
            actor_id=actor_id,
            subject_type="pull_request",
            subject_id=pr_id,
            event_type="pull_request.opened",
        ),
        EventRecord(
            repo_id=repo_id,
            occurred_at=pr.get("created_at"),
            actor_id=actor_id,
            subject_type="pull_request",
            subject_id=pr_id,
            event_type="pull_request.head.set",
            commit_sha=(pr.get("head") or {}).get("sha"),
            payload={"head_ref": (pr.get("head") or {}).get("ref")},
        ),
        EventRecord(
            repo_id=repo_id,
            occurred_at=pr.get("created_at"),
            actor_id=actor_id,
            subject_type="pull_request",
            subject_id=pr_id,
            event_type="pull_request.draft.set",
            payload={"is_draft": bool(pr.get("draft"))},
        ),
    ]
    if pr.get("closed_at") and not pr.get("merged_at"):
        events.append(
            EventRecord(
                repo_id=repo_id,
                occurred_at=pr.get("closed_at"),
                actor_id=actor_id,
                subject_type="pull_request",
                subject_id=pr_id,
                event_type="pull_request.closed",
            )
        )
    if pr.get("merged_at"):
        events.append(
            EventRecord(
                repo_id=repo_id,
                occurred_at=pr.get("merged_at"),
                actor_id=actor_id,
                subject_type="pull_request",
                subject_id=pr_id,
                event_type="pull_request.merged",
                commit_sha=pr.get("merge_commit_sha"),
            )
        )
    return events


def normalize_issue_event(
    issue_id: int,
    repo_id: int,
    payload: dict,
    pull_request_id: int | None = None,
) -> list[EventRecord]:
    event_type = payload.get("event")
    occurred_at = payload.get("created_at")
    actor_id = (payload.get("actor") or {}).get("id")
    is_pull_request = pull_request_id is not None

    if event_type == "labeled":
        label = payload.get("label") or {}
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="issue",
                subject_id=issue_id,
                event_type="issue.label.add",
                object_type="label",
                object_id=label.get("id"),
            )
        ]
    if event_type == "unlabeled":
        label = payload.get("label") or {}
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="issue",
                subject_id=issue_id,
                event_type="issue.label.remove",
                object_type="label",
                object_id=label.get("id"),
            )
        ]
    if event_type == "assigned":
        assignee = payload.get("assignee") or {}
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="issue",
                subject_id=issue_id,
                event_type="issue.assignee.add",
                object_type="user",
                object_id=assignee.get("id"),
            )
        ]
    if event_type == "unassigned":
        assignee = payload.get("assignee") or {}
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="issue",
                subject_id=issue_id,
                event_type="issue.assignee.remove",
                object_type="user",
                object_id=assignee.get("id"),
            )
        ]
    if event_type == "milestoned":
        milestone = payload.get("milestone") or {}
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="issue",
                subject_id=issue_id,
                event_type="issue.milestone.set",
                object_type="milestone",
                object_id=milestone.get("id"),
            )
        ]
    if event_type == "demilestoned":
        milestone = payload.get("milestone") or {}
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="issue",
                subject_id=issue_id,
                event_type="issue.milestone.clear",
                object_type="milestone",
                object_id=milestone.get("id"),
            )
        ]
    if event_type == "closed":
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="issue",
                subject_id=issue_id,
                event_type="issue.closed",
            )
        ]
    if event_type == "reopened":
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="issue",
                subject_id=issue_id,
                event_type="issue.reopened",
            )
        ]
    if event_type == "edited":
        title = payload.get("title")
        body = payload.get("body")
        issue_payload = payload.get("issue") or {}
        title = issue_payload.get("title") if title is None else title
        body = issue_payload.get("body") if body is None else body
        if title is not None or body is not None:
            return [
                EventRecord(
                    repo_id=repo_id,
                    occurred_at=occurred_at,
                    actor_id=actor_id,
                    subject_type="issue",
                    subject_id=issue_id,
                    event_type="issue.content.edit",
                    payload={"title": title, "body": body},
                )
            ]
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="issue",
                subject_id=issue_id,
                event_type="issue.edited",
                payload=payload,
            )
        ]
    if event_type == "renamed":
        rename = payload.get("rename") or {}
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="issue",
                subject_id=issue_id,
                event_type="issue.content.edit",
                payload={"title": rename.get("to")},
            )
        ]
    if event_type == "commented":
        comment = payload.get("comment") or {}
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="issue",
                subject_id=issue_id,
                event_type="issue.commented",
                object_type="comment",
                object_id=comment.get("id") or payload.get("comment_id"),
                payload={"body": comment.get("body")},
            )
        ]
    if event_type == "review_requested" and pull_request_id:
        reviewer = payload.get("requested_reviewer") or {}
        team = payload.get("requested_team") or {}
        if reviewer:
            reviewer_type = "user"
            reviewer_id = reviewer.get("id")
        else:
            reviewer_type = "team"
            reviewer_id = team.get("id")
        if reviewer_id is None:
            return []
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="pull_request",
                subject_id=pull_request_id,
                event_type="pull_request.review_request.add",
                object_type=reviewer_type,
                object_id=reviewer_id,
            )
        ]
    if event_type == "review_request_removed" and pull_request_id:
        reviewer = payload.get("requested_reviewer") or {}
        team = payload.get("requested_team") or {}
        if reviewer:
            reviewer_type = "user"
            reviewer_id = reviewer.get("id")
        else:
            reviewer_type = "team"
            reviewer_id = team.get("id")
        if reviewer_id is None:
            return []
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="pull_request",
                subject_id=pull_request_id,
                event_type="pull_request.review_request.remove",
                object_type=reviewer_type,
                object_id=reviewer_id,
            )
        ]
    if event_type == "ready_for_review" and pull_request_id:
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="pull_request",
                subject_id=pull_request_id,
                event_type="pull_request.draft.set",
                payload={"is_draft": False},
            )
        ]
    if event_type == "converted_to_draft" and pull_request_id:
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="pull_request",
                subject_id=pull_request_id,
                event_type="pull_request.draft.set",
                payload={"is_draft": True},
            )
        ]
    if event_type == "synchronize" and pull_request_id:
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="pull_request",
                subject_id=pull_request_id,
                event_type="pull_request.head.set",
                commit_sha=payload.get("commit_id"),
            )
        ]
    if event_type == "merged" and pull_request_id:
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="pull_request",
                subject_id=pull_request_id,
                event_type="pull_request.merged",
                commit_sha=payload.get("commit_id"),
            )
        ]
    if event_type == "review_dismissed" and pull_request_id:
        dismissed = payload.get("dismissed_review") or {}
        review_id = dismissed.get("review_id") or dismissed.get("id") or payload.get(
            "review_id"
        )
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="pull_request",
                subject_id=pull_request_id,
                event_type="review.dismissed",
                object_type="review",
                object_id=review_id,
                payload=payload,
            )
        ]
    if event_type in {"head_ref_deleted", "head_ref_restored"} and pull_request_id:
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="pull_request",
                subject_id=pull_request_id,
                event_type=f"pull_request.{event_type}",
                payload=payload,
            )
        ]
    if event_type in {"head_ref_force_pushed", "base_ref_force_pushed"} and pull_request_id:
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="pull_request",
                subject_id=pull_request_id,
                event_type=f"pull_request.{event_type}",
                payload=payload,
            )
        ]
    if event_type in {"locked", "unlocked", "pinned", "unpinned"}:
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="issue",
                subject_id=issue_id,
                event_type=f"issue.{event_type}",
                payload=payload,
            )
        ]
    if event_type in {"subscribed", "unsubscribed", "mentioned"}:
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="issue",
                subject_id=issue_id,
                event_type=f"issue.{event_type}",
                payload=payload,
            )
        ]
    if event_type in {"referenced", "cross-referenced"}:
        object_type = None
        object_id = None
        source = payload.get("source") or {}
        source_issue = source.get("issue") or {}
        if source_issue.get("id"):
            object_type = "issue"
            object_id = source_issue.get("id")
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="issue",
                subject_id=issue_id,
                event_type=f"issue.{event_type}",
                object_type=object_type,
                object_id=object_id,
                commit_sha=payload.get("commit_id"),
                payload=payload,
            )
        ]
    if event_type in {"transferred", "added_to_project", "removed_from_project"}:
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="issue",
                subject_id=issue_id,
                event_type=f"issue.{event_type}",
                payload=payload,
            )
        ]
    if event_type == "opened":
        return [
            EventRecord(
                repo_id=repo_id,
                occurred_at=occurred_at,
                actor_id=actor_id,
                subject_type="issue",
                subject_id=issue_id,
                event_type="issue.opened",
            )
        ]
    if not event_type:
        return []
    subject_type = "pull_request" if is_pull_request else "issue"
    subject_id = pull_request_id if is_pull_request else issue_id
    return [
        EventRecord(
            repo_id=repo_id,
            occurred_at=occurred_at,
            actor_id=actor_id,
            subject_type=subject_type,
            subject_id=subject_id,
            event_type=f"{subject_type}.event.{event_type}",
            payload=payload,
        )
    ]


def normalize_issue_comment(
    comment: dict,
    repo_id: int,
    issue_id: int,
) -> list[EventRecord]:
    actor_id = (comment.get("user") or {}).get("id")
    created = comment.get("created_at")
    updated = comment.get("updated_at")
    created_dt = parse_datetime(created) if created else None
    events = [
        EventRecord(
            repo_id=repo_id,
            occurred_at=created,
            actor_id=actor_id,
            subject_type="comment",
            subject_id=comment.get("id"),
            event_type="comment.created",
            object_type="issue",
            object_id=issue_id,
            payload={"body": comment.get("body")},
        )
    ]
    if updated and created_dt and parse_datetime(updated) > created_dt:
        events.append(
            EventRecord(
                repo_id=repo_id,
                occurred_at=updated,
                actor_id=actor_id,
                subject_type="comment",
                subject_id=comment.get("id"),
                event_type="comment.edited",
                object_type="issue",
                object_id=issue_id,
                payload={"body": comment.get("body")},
            )
        )
    return events


def normalize_review(review: dict, repo_id: int, pr_id: int) -> list[EventRecord]:
    actor_id = (review.get("user") or {}).get("id")
    return [
        EventRecord(
            repo_id=repo_id,
            occurred_at=review.get("submitted_at"),
            actor_id=actor_id,
            subject_type="review",
            subject_id=review.get("id"),
            event_type="review.submitted",
            object_type="pull_request",
            object_id=pr_id,
            commit_sha=review.get("commit_id"),
            payload={"body": review.get("body"), "state": review.get("state")},
        )
    ]


def normalize_review_comment(
    comment: dict, repo_id: int, pr_id: int, review_id: int | None
) -> list[EventRecord]:
    actor_id = (comment.get("user") or {}).get("id")
    created = comment.get("created_at")
    updated = comment.get("updated_at")
    created_dt = parse_datetime(created) if created else None
    events = [
        EventRecord(
            repo_id=repo_id,
            occurred_at=created,
            actor_id=actor_id,
            subject_type="comment",
            subject_id=comment.get("id"),
            event_type="comment.created",
            object_type="pull_request",
            object_id=pr_id,
            payload={"body": comment.get("body"), "review_id": review_id},
        )
    ]
    if updated and created_dt and parse_datetime(updated) > created_dt:
        events.append(
            EventRecord(
                repo_id=repo_id,
                occurred_at=updated,
                actor_id=actor_id,
                subject_type="comment",
                subject_id=comment.get("id"),
                event_type="comment.edited",
                object_type="pull_request",
                object_id=pr_id,
                payload={"body": comment.get("body"), "review_id": review_id},
            )
        )
    return events
