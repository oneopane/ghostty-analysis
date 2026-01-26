import pytest
from sqlalchemy import func, select

from gh_history_ingestion.ingest.backfill import backfill_repo
from gh_history_ingestion.storage.db import get_engine, get_session, init_db
from gh_history_ingestion.storage.schema import (
    Comment,
    Commit,
    Event,
    Issue,
    PullRequest,
    Ref,
    Release,
    Repo,
    Review,
)


class StubGitHubClient:
    def __init__(self):
        self.calls = []

    async def get_json(self, path, params=None):
        self.calls.append((path, params))
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
        self.calls.append((path, params))
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
                    "id": 100,
                    "number": 1,
                    "title": "Issue",
                    "body": "Issue body",
                    "state": "open",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                    "user": {"id": 2, "login": "octo"},
                },
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
                },
            ]:
                yield item
            return
        if path == "/repos/octo/repo/commits":
            for item in [
                {
                    "sha": "c1",
                    "commit": {
                        "author": {
                            "name": "alice",
                            "email": "alice@example.com",
                            "date": "2024-01-01T03:00:00Z",
                        },
                        "committer": {
                            "name": "bob",
                            "email": "bob@example.com",
                            "date": "2024-01-01T04:00:00Z",
                        },
                        "message": "initial commit",
                    },
                    "author": {"id": 10, "login": "alice"},
                    "committer": {"id": 11, "login": "bob"},
                }
            ]:
                yield item
            return
        if path == "/repos/octo/repo/branches":
            for item in [
                {
                    "name": "main",
                    "protected": True,
                    "commit": {"sha": "c1"},
                }
            ]:
                yield item
            return
        if path == "/repos/octo/repo/tags":
            for item in [
                {
                    "name": "v1.0",
                    "commit": {"sha": "c1"},
                }
            ]:
                yield item
            return
        if path == "/repos/octo/repo/releases":
            for item in [
                {
                    "id": 900,
                    "tag_name": "v1.0",
                    "name": "v1.0",
                    "draft": False,
                    "prerelease": False,
                    "created_at": "2024-01-03T00:00:00Z",
                    "published_at": "2024-01-04T00:00:00Z",
                    "author": {"id": 2, "login": "octo"},
                    "body": "notes",
                }
            ]:
                yield item
            return
        if path == "/repos/octo/repo/issues/1/events":
            for item in [
                {
                    "id": 1,
                    "event": "opened",
                    "created_at": "2024-01-01T00:00:00Z",
                    "actor": {"id": 2, "login": "octo"},
                }
            ]:
                yield item
            return
        if path == "/repos/octo/repo/issues/1/comments":
            for item in [
                {
                    "id": 500,
                    "body": "comment",
                    "created_at": "2024-01-01T01:00:00Z",
                    "updated_at": "2024-01-01T01:00:00Z",
                    "user": {"id": 2, "login": "octo"},
                }
            ]:
                yield item
            return
        if path == "/repos/octo/repo/issues/2/events":
            for item in [
                {
                    "id": 2,
                    "event": "review_requested",
                    "created_at": "2024-01-02T00:00:00Z",
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
async def test_backfill_orchestration(tmp_path):
    db_path = tmp_path / "backfill.db"
    client = StubGitHubClient()
    await backfill_repo("octo/repo", db_path, client=client)

    engine = get_engine(db_path)
    init_db(engine)
    session = get_session(engine)

    assert session.scalar(select(func.count()).select_from(Repo)) == 1
    assert session.scalar(select(func.count()).select_from(Issue)) == 2
    assert session.scalar(select(func.count()).select_from(PullRequest)) == 1
    assert session.scalar(select(func.count()).select_from(Comment)) == 1
    assert session.scalar(select(func.count()).select_from(Review)) == 1
    assert session.scalar(select(func.count()).select_from(Commit)) == 1
    assert session.scalar(select(func.count()).select_from(Ref)) == 2
    assert session.scalar(select(func.count()).select_from(Release)) == 1
    assert session.scalar(select(func.count()).select_from(Event)) >= 3


@pytest.mark.asyncio
async def test_backfill_time_window_filters(tmp_path):
    db_path = tmp_path / "backfill-window.db"
    client = StubGitHubClient()
    await backfill_repo(
        "octo/repo",
        db_path,
        client=client,
        start_at="2024-01-02T00:00:00Z",
    )

    engine = get_engine(db_path)
    init_db(engine)
    session = get_session(engine)

    assert session.scalar(select(func.count()).select_from(Commit)) == 0
    assert session.scalar(select(func.count()).select_from(Issue)) == 1
    assert session.scalar(select(Issue.number)) == 2
    assert session.scalar(select(func.count()).select_from(Event)) >= 1
