from __future__ import annotations

from ..event_record import EventRecord


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
