from __future__ import annotations

import json

from sqlalchemy import delete, select, update

from ..storage.schema import (
    Comment,
    CommentContentInterval,
    Event,
    Issue,
    IssueAssigneeInterval,
    IssueContentInterval,
    IssueLabelInterval,
    IssueMilestoneInterval,
    IssueStateInterval,
    PullRequest,
    PullRequestDraftInterval,
    PullRequestHeadInterval,
    PullRequestReviewRequestInterval,
    Review,
    ReviewContentInterval,
)


def rebuild_intervals(session, repo_id: int) -> None:
    issue_ids = session.scalars(select(Issue.id).where(Issue.repo_id == repo_id)).all()
    pr_ids = session.scalars(select(PullRequest.id).where(PullRequest.repo_id == repo_id)).all()
    review_ids = session.scalars(select(Review.id).where(Review.repo_id == repo_id)).all()
    comment_ids = session.scalars(select(Comment.id).where(Comment.repo_id == repo_id)).all()

    for model, ids, field in [
        (IssueStateInterval, issue_ids, IssueStateInterval.issue_id),
        (IssueContentInterval, issue_ids, IssueContentInterval.issue_id),
        (IssueLabelInterval, issue_ids, IssueLabelInterval.issue_id),
        (IssueAssigneeInterval, issue_ids, IssueAssigneeInterval.issue_id),
        (IssueMilestoneInterval, issue_ids, IssueMilestoneInterval.issue_id),
        (PullRequestDraftInterval, pr_ids, PullRequestDraftInterval.pull_request_id),
        (PullRequestHeadInterval, pr_ids, PullRequestHeadInterval.pull_request_id),
        (
            PullRequestReviewRequestInterval,
            pr_ids,
            PullRequestReviewRequestInterval.pull_request_id,
        ),
        (CommentContentInterval, comment_ids, CommentContentInterval.comment_id),
        (ReviewContentInterval, review_ids, ReviewContentInterval.review_id),
    ]:
        if ids:
            session.execute(delete(model).where(field.in_(ids)))

    events = session.scalars(
        select(Event)
        .where(Event.repo_id == repo_id)
        .order_by(Event.occurred_at, Event.id)
    ).all()

    for event in events:
        payload = json.loads(event.payload_json) if event.payload_json else {}
        if event.event_type in {"issue.opened", "issue.reopened"}:
            _close_issue_state(session, event.subject_id, event.id)
            session.add(
                IssueStateInterval(
                    issue_id=event.subject_id,
                    state="open",
                    start_event_id=event.id,
                )
            )
        elif event.event_type == "issue.closed":
            _close_issue_state(session, event.subject_id, event.id)
            session.add(
                IssueStateInterval(
                    issue_id=event.subject_id,
                    state="closed",
                    start_event_id=event.id,
                )
            )
        elif event.event_type in {"issue.content.set", "issue.content.edit"}:
            session.execute(
                update(IssueContentInterval)
                .where(
                    IssueContentInterval.issue_id == event.subject_id,
                    IssueContentInterval.end_event_id.is_(None),
                )
                .values(end_event_id=event.id)
            )
            session.add(
                IssueContentInterval(
                    issue_id=event.subject_id,
                    title=payload.get("title"),
                    body=payload.get("body"),
                    start_event_id=event.id,
                )
            )
        elif event.event_type == "issue.label.add":
            session.add(
                IssueLabelInterval(
                    issue_id=event.subject_id,
                    label_id=event.object_id,
                    start_event_id=event.id,
                )
            )
        elif event.event_type == "issue.label.remove":
            session.execute(
                update(IssueLabelInterval)
                .where(
                    IssueLabelInterval.issue_id == event.subject_id,
                    IssueLabelInterval.label_id == event.object_id,
                    IssueLabelInterval.end_event_id.is_(None),
                )
                .values(end_event_id=event.id)
            )
        elif event.event_type == "issue.assignee.add":
            session.add(
                IssueAssigneeInterval(
                    issue_id=event.subject_id,
                    user_id=event.object_id,
                    start_event_id=event.id,
                )
            )
        elif event.event_type == "issue.assignee.remove":
            session.execute(
                update(IssueAssigneeInterval)
                .where(
                    IssueAssigneeInterval.issue_id == event.subject_id,
                    IssueAssigneeInterval.user_id == event.object_id,
                    IssueAssigneeInterval.end_event_id.is_(None),
                )
                .values(end_event_id=event.id)
            )
        elif event.event_type == "issue.milestone.set":
            session.add(
                IssueMilestoneInterval(
                    issue_id=event.subject_id,
                    milestone_id=event.object_id,
                    start_event_id=event.id,
                )
            )
        elif event.event_type == "issue.milestone.clear":
            session.execute(
                update(IssueMilestoneInterval)
                .where(
                    IssueMilestoneInterval.issue_id == event.subject_id,
                    IssueMilestoneInterval.milestone_id == event.object_id,
                    IssueMilestoneInterval.end_event_id.is_(None),
                )
                .values(end_event_id=event.id)
            )
        elif event.event_type == "pull_request.draft.set":
            session.execute(
                update(PullRequestDraftInterval)
                .where(
                    PullRequestDraftInterval.pull_request_id == event.subject_id,
                    PullRequestDraftInterval.end_event_id.is_(None),
                )
                .values(end_event_id=event.id)
            )
            session.add(
                PullRequestDraftInterval(
                    pull_request_id=event.subject_id,
                    is_draft=bool(payload.get("is_draft")),
                    start_event_id=event.id,
                )
            )
        elif event.event_type == "pull_request.head.set":
            session.execute(
                update(PullRequestHeadInterval)
                .where(
                    PullRequestHeadInterval.pull_request_id == event.subject_id,
                    PullRequestHeadInterval.end_event_id.is_(None),
                )
                .values(end_event_id=event.id)
            )
            session.add(
                PullRequestHeadInterval(
                    pull_request_id=event.subject_id,
                    head_sha=event.commit_sha,
                    head_ref=payload.get("head_ref"),
                    start_event_id=event.id,
                )
            )
        elif event.event_type == "pull_request.review_request.add":
            session.add(
                PullRequestReviewRequestInterval(
                    pull_request_id=event.subject_id,
                    reviewer_type=event.object_type,
                    reviewer_id=event.object_id,
                    start_event_id=event.id,
                )
            )
        elif event.event_type == "pull_request.review_request.remove":
            session.execute(
                update(PullRequestReviewRequestInterval)
                .where(
                    PullRequestReviewRequestInterval.pull_request_id == event.subject_id,
                    PullRequestReviewRequestInterval.reviewer_id == event.object_id,
                    PullRequestReviewRequestInterval.end_event_id.is_(None),
                )
                .values(end_event_id=event.id)
            )
        elif event.event_type == "comment.created":
            session.add(
                CommentContentInterval(
                    comment_id=event.subject_id,
                    body=payload.get("body"),
                    start_event_id=event.id,
                )
            )
        elif event.event_type == "comment.edited":
            session.execute(
                update(CommentContentInterval)
                .where(
                    CommentContentInterval.comment_id == event.subject_id,
                    CommentContentInterval.end_event_id.is_(None),
                )
                .values(end_event_id=event.id)
            )
            session.add(
                CommentContentInterval(
                    comment_id=event.subject_id,
                    body=payload.get("body"),
                    start_event_id=event.id,
                )
            )
        elif event.event_type == "comment.deleted":
            session.execute(
                update(CommentContentInterval)
                .where(
                    CommentContentInterval.comment_id == event.subject_id,
                    CommentContentInterval.end_event_id.is_(None),
                )
                .values(end_event_id=event.id)
            )
        elif event.event_type in {"review.submitted", "review.edited"}:
            session.execute(
                update(ReviewContentInterval)
                .where(
                    ReviewContentInterval.review_id == event.subject_id,
                    ReviewContentInterval.end_event_id.is_(None),
                )
                .values(end_event_id=event.id)
            )
            session.add(
                ReviewContentInterval(
                    review_id=event.subject_id,
                    body=payload.get("body"),
                    state=payload.get("state"),
                    start_event_id=event.id,
                )
            )

    session.commit()


def _close_issue_state(session, issue_id: int, end_event_id: int) -> None:
    session.execute(
        update(IssueStateInterval)
        .where(
            IssueStateInterval.issue_id == issue_id,
            IssueStateInterval.end_event_id.is_(None),
        )
        .values(end_event_id=end_event_id)
    )
