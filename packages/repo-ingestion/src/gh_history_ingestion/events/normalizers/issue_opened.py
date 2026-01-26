from __future__ import annotations

from ..event_record import EventRecord


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
