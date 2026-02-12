from __future__ import annotations

from ..event_record import EventRecord
from ...utils.time import parse_datetime


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
