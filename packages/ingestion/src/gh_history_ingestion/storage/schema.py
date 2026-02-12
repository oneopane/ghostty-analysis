from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Repo(Base):
    __tablename__ = "repos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    owner_login: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    is_private: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_branch: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    disabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    login: Mapped[str | None] = mapped_column(String, nullable=True)
    type: Mapped[str | None] = mapped_column(String, nullable=True)
    site_admin: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    slug: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)


class Label(Base):
    __tablename__ = "labels"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    repo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("repos.id"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    color: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class Milestone(Base):
    __tablename__ = "milestones"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    repo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("repos.id"))
    number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    state: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    repo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("repos.id"))
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_pull_request: Mapped[bool] = mapped_column(Boolean, default=False)
    locked: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    __table_args__ = (UniqueConstraint("repo_id", "number", name="uq_issue_number"),)


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    repo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("repos.id"))
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    issue_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("issues.id"))
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str | None] = mapped_column(String, nullable=True)
    draft: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    merged: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    merge_commit_sha: Mapped[str | None] = mapped_column(String, nullable=True)
    head_sha: Mapped[str | None] = mapped_column(String, nullable=True)
    head_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    base_sha: Mapped[str | None] = mapped_column(String, nullable=True)
    base_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("repo_id", "number", name="uq_pr_number"),)


class PullRequestFile(Base):
    __tablename__ = "pull_request_files"

    repo_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("repos.id"), primary_key=True
    )
    pull_request_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pull_requests.id"), primary_key=True
    )
    head_sha: Mapped[str] = mapped_column(String, primary_key=True)
    path: Mapped[str] = mapped_column(String, primary_key=True)

    status: Mapped[str | None] = mapped_column(String, nullable=True)
    additions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deletions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    changes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index(
            "ix_pr_files_repo_pr_head",
            "repo_id",
            "pull_request_id",
            "head_sha",
        ),
        Index("ix_pr_files_repo_path", "repo_id", "path"),
    )


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    repo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("repos.id"))
    pull_request_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pull_requests.id")
    )
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    state: Mapped[str | None] = mapped_column(String, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    commit_id: Mapped[str | None] = mapped_column(String, nullable=True)


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    repo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("repos.id"))
    issue_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("issues.id"))
    pull_request_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("pull_requests.id")
    )
    review_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("reviews.id"))
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    path: Mapped[str | None] = mapped_column(String, nullable=True)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commit_id: Mapped[str | None] = mapped_column(String, nullable=True)
    in_reply_to_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    comment_type: Mapped[str | None] = mapped_column(String, nullable=True)


class Commit(Base):
    __tablename__ = "commits"

    repo_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("repos.id"), primary_key=True
    )
    sha: Mapped[str] = mapped_column(String, primary_key=True)
    author_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    committer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    author_name: Mapped[str | None] = mapped_column(String, nullable=True)
    author_email: Mapped[str | None] = mapped_column(String, nullable=True)
    committer_name: Mapped[str | None] = mapped_column(String, nullable=True)
    committer_email: Mapped[str | None] = mapped_column(String, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    authored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Ref(Base):
    __tablename__ = "refs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("repos.id"))
    ref_type: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    sha: Mapped[str | None] = mapped_column(String, nullable=True)
    is_protected: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    __table_args__ = (UniqueConstraint("repo_id", "ref_type", "name", name="uq_ref"),)


class Release(Base):
    __tablename__ = "releases"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    repo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("repos.id"))
    tag_name: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    draft: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    prerelease: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    author_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_commitish: Mapped[str | None] = mapped_column(String, nullable=True)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("repos.id"))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    actor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    subject_type: Mapped[str] = mapped_column(String, nullable=False)
    subject_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    object_type: Mapped[str | None] = mapped_column(String, nullable=True)
    object_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String, nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_key: Mapped[str] = mapped_column(String, nullable=False, unique=True)


class Watermark(Base):
    __tablename__ = "watermarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("repos.id"))
    resource: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    etag: Mapped[str | None] = mapped_column(String, nullable=True)
    last_modified: Mapped[str | None] = mapped_column(String, nullable=True)
    cursor: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (UniqueConstraint("repo_id", "resource", name="uq_watermark"),)


class IngestionGap(Base):
    __tablename__ = "ingestion_gaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("repos.id"))
    resource: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class QaReport(Base):
    __tablename__ = "qa_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("repos.id"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class IssueStateInterval(Base):
    __tablename__ = "issue_state_intervals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("issues.id"))
    state: Mapped[str] = mapped_column(String, nullable=False)
    start_event_id: Mapped[int] = mapped_column(Integer, ForeignKey("events.id"))
    end_event_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("events.id"))


class IssueContentInterval(Base):
    __tablename__ = "issue_content_intervals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("issues.id"))
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_event_id: Mapped[int] = mapped_column(Integer, ForeignKey("events.id"))
    end_event_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("events.id"))


class IssueLabelInterval(Base):
    __tablename__ = "issue_label_intervals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("issues.id"))
    label_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("labels.id"))
    start_event_id: Mapped[int] = mapped_column(Integer, ForeignKey("events.id"))
    end_event_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("events.id"))


class IssueAssigneeInterval(Base):
    __tablename__ = "issue_assignee_intervals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("issues.id"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    start_event_id: Mapped[int] = mapped_column(Integer, ForeignKey("events.id"))
    end_event_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("events.id"))


class IssueMilestoneInterval(Base):
    __tablename__ = "issue_milestone_intervals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("issues.id"))
    milestone_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("milestones.id"))
    start_event_id: Mapped[int] = mapped_column(Integer, ForeignKey("events.id"))
    end_event_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("events.id"))


class PullRequestDraftInterval(Base):
    __tablename__ = "pull_request_draft_intervals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pull_request_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pull_requests.id")
    )
    is_draft: Mapped[bool] = mapped_column(Boolean, nullable=False)
    start_event_id: Mapped[int] = mapped_column(Integer, ForeignKey("events.id"))
    end_event_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("events.id"))


class PullRequestHeadInterval(Base):
    __tablename__ = "pull_request_head_intervals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pull_request_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pull_requests.id")
    )
    head_sha: Mapped[str | None] = mapped_column(String, nullable=True)
    head_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    start_event_id: Mapped[int] = mapped_column(Integer, ForeignKey("events.id"))
    end_event_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("events.id"))


class PullRequestReviewRequestInterval(Base):
    __tablename__ = "pull_request_review_request_intervals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pull_request_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pull_requests.id")
    )
    reviewer_type: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewer_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    start_event_id: Mapped[int] = mapped_column(Integer, ForeignKey("events.id"))
    end_event_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("events.id"))


class CommentContentInterval(Base):
    __tablename__ = "comment_content_intervals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("comments.id"))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_event_id: Mapped[int] = mapped_column(Integer, ForeignKey("events.id"))
    end_event_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("events.id"))


class ReviewContentInterval(Base):
    __tablename__ = "review_content_intervals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("reviews.id"))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str | None] = mapped_column(String, nullable=True)
    start_event_id: Mapped[int] = mapped_column(Integer, ForeignKey("events.id"))
    end_event_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("events.id"))


class ObjectSnapshot(Base):
    __tablename__ = "object_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(Integer, ForeignKey("events.id"))
    object_type: Mapped[str] = mapped_column(String, nullable=False)
    object_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
