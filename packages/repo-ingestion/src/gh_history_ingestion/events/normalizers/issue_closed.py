from __future__ import annotations

from ..event_record import EventRecord


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
