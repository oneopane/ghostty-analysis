import pytest
from sqlalchemy import func, select

from gh_history_ingestion.ingest.pull_requests import backfill_pull_requests
from gh_history_ingestion.storage.db import get_engine, get_session, init_db
from gh_history_ingestion.storage.schema import (
    PullRequest,
    PullRequestFile,
    PullRequestReviewRequestInterval,
    Repo,
    Review,
)


class StubPullRequestsClient:
    def __init__(self):
        self.calls = []

    async def get_json(self, path, params=None):
        self.calls.append(("get_json", path, params))
        if path == "/repos/octo/repo":
            return {
                "id": 1,
                "name": "repo",
                "full_name": "octo/repo",
                "owner": {"id": 2, "login": "octo", "type": "User"},
                "private": False,
                "default_branch": "main",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z",
                "pushed_at": "2024-01-02T00:00:00Z",
            }
        raise AssertionError(f"Unexpected get_json: {path}")

    async def paginate(
        self,
        path,
        params=None,
        headers=None,
        on_gap=None,
        on_response=None,
        resource=None,
        max_pages=None,
    ):
        self.calls.append(("paginate", path, params))
        if path == "/repos/octo/repo/pulls":
            for item in [
                {
                    "id": 200,
                    "number": 2,
                    "title": "PR",
                    "body": "PR body",
                    "state": "open",
                    "draft": False,
                    "created_at": "2024-01-02T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "user": {"id": 3, "login": "pr-author"},
                    "head": {"sha": "abc", "ref": "feat"},
                    "base": {"sha": "def", "ref": "main"},
                }
            ]:
                yield item
            return

        if path == "/repos/octo/repo/issues":
            for item in [
                {
                    "id": 101,
                    "number": 2,
                    "title": "PR",
                    "body": "PR body",
                    "state": "open",
                    "created_at": "2024-01-02T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "user": {"id": 3, "login": "pr-author"},
                    "pull_request": {"url": "https://api.github.com/..."},
                }
            ]:
                yield item
            return

        if path == "/repos/octo/repo/pulls/2/files":
            for item in [{"filename": "README.md", "status": "modified"}]:
                yield item
            return

        if path == "/repos/octo/repo/issues/2/events":
            for item in [
                {
                    "id": 1,
                    "event": "review_requested",
                    "created_at": "2024-01-02T00:10:00Z",
                    "actor": {"id": 3, "login": "pr-author"},
                    "requested_reviewer": {"id": 4, "login": "reviewer"},
                }
            ]:
                yield item
            return

        if path == "/repos/octo/repo/issues/2/comments":
            if False:
                yield None
            return

        if path == "/repos/octo/repo/pulls/2/reviews":
            for item in [
                {
                    "id": 700,
                    "user": {"id": 4, "login": "reviewer"},
                    "state": "approved",
                    "body": "LGTM",
                    "submitted_at": "2024-01-02T02:00:00Z",
                    "commit_id": "abc",
                }
            ]:
                yield item
            return

        if path == "/repos/octo/repo/pulls/2/comments":
            if False:
                yield None
            return

        raise AssertionError(f"Unexpected paginate: {path}")


@pytest.mark.asyncio
async def test_pull_requests_backfill_with_truth(tmp_path):
    db_path = tmp_path / "pr-window.db"
    client = StubPullRequestsClient()
    await backfill_pull_requests(
        "octo/repo",
        db_path,
        client=client,
        with_truth=True,
        start_at=None,
        end_at=None,
    )

    engine = get_engine(db_path)
    init_db(engine)
    session = get_session(engine)

    assert session.scalar(select(func.count()).select_from(Repo)) == 1
    assert session.scalar(select(func.count()).select_from(PullRequest)) == 1
    assert session.scalar(select(func.count()).select_from(PullRequestFile)) == 1
    assert session.scalar(select(func.count()).select_from(Review)) == 1
    assert (
        session.scalar(
            select(func.count()).select_from(PullRequestReviewRequestInterval)
        )
        >= 1
    )


@pytest.mark.asyncio
async def test_pull_requests_backfill_without_truth(tmp_path):
    db_path = tmp_path / "pr-window-lite.db"
    client = StubPullRequestsClient()
    await backfill_pull_requests(
        "octo/repo",
        db_path,
        client=client,
        with_truth=False,
        start_at=None,
        end_at=None,
    )

    engine = get_engine(db_path)
    init_db(engine)
    session = get_session(engine)
    assert session.scalar(select(func.count()).select_from(Review)) == 0
