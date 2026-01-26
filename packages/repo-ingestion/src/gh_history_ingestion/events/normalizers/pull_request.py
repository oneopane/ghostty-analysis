from __future__ import annotations

from ..event_record import EventRecord


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
