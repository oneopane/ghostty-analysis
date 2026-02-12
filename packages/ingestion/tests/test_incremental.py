import pytest
from sqlalchemy import select

from gh_history_ingestion.ingest.incremental import incremental_update
from gh_history_ingestion.storage.db import get_engine, get_session, init_db
from gh_history_ingestion.storage.schema import (
    Commit,
    IngestionCheckpoint,
    Issue,
    PullRequest,
    PullRequestFile,
    Repo,
    Watermark,
)
from gh.storage.upsert import (
    upsert_ingestion_checkpoint,
    upsert_repo,
)
from gh_history_ingestion.utils.time import parse_datetime


class StubIncrementalClient:
    def __init__(self):
        self.calls = []

    async def get_json(self, path, params=None):
        self.calls.append((path, params, None))
        if path == "/repos/octo/repo":
            return {
                "id": 1,
                "name": "repo",
                "full_name": "octo/repo",
                "owner": {"id": 2, "login": "octo", "type": "User"},
                "private": False,
                "default_branch": "main",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-10T00:00:00Z",
                "pushed_at": "2024-01-10T00:00:00Z",
            }
        raise AssertionError(f"Unexpected get_json: {path}")

    async def paginate_conditional(
        self,
        path,
        params=None,
        headers=None,
        resource=None,
        on_gap=None,
        on_response=None,
    ):
        self.calls.append((path, params, headers))
        if path == "/repos/octo/repo/issues":
            for item in [
                {
                    "id": 100,
                    "number": 1,
                    "title": "Issue",
                    "body": "Issue body",
                    "state": "open",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-05T00:00:00Z",
                    "user": {"id": 2, "login": "octo"},
                }
            ]:
                yield item
            return
        if path == "/repos/octo/repo/pulls":
            for item in [
                {
                    "id": 200,
                    "number": 1,
                    "title": "PR",
                    "body": "PR body",
                    "state": "open",
                    "draft": False,
                    "created_at": "2024-01-02T00:00:00Z",
                    "updated_at": "2024-01-06T00:00:00Z",
                    "user": {"id": 2, "login": "octo"},
                    "head": {"sha": "abc", "ref": "feat"},
                    "base": {"sha": "def", "ref": "main"},
                }
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
                            "date": "2024-01-07T00:00:00Z",
                        },
                        "committer": {
                            "name": "bob",
                            "email": "bob@example.com",
                            "date": "2024-01-07T00:00:00Z",
                        },
                        "message": "incremental",
                    },
                    "author": {"id": 10, "login": "alice"},
                    "committer": {"id": 11, "login": "bob"},
                }
            ]:
                yield item
            return
        if path == "/repos/octo/repo/branches":
            if False:
                yield None
            return
        if path == "/repos/octo/repo/tags":
            if False:
                yield None
            return
        if path == "/repos/octo/repo/releases":
            if False:
                yield None
            return
        raise AssertionError(f"Unexpected paginate_conditional: {path}")

    async def paginate(
        self,
        path,
        params=None,
        headers=None,
        on_gap=None,
        resource=None,
        max_pages=None,
    ):
        self.calls.append((path, params, headers))
        if path == "/repos/octo/repo/pulls/1/files":
            for item in [
                {
                    "filename": "README.md",
                    "status": "modified",
                    "additions": 1,
                    "deletions": 0,
                    "changes": 1,
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
            if False:
                yield None
            return
        if path == "/repos/octo/repo/pulls/1/reviews":
            if False:
                yield None
            return
        if path == "/repos/octo/repo/pulls/1/comments":
            if False:
                yield None
            return
        if path == "/repos/octo/repo/branches":
            if False:
                yield None
            return
        if path == "/repos/octo/repo/tags":
            if False:
                yield None
            return
        if path == "/repos/octo/repo/releases":
            if False:
                yield None
            return
        raise AssertionError(f"Unexpected paginate: {path}")


@pytest.mark.asyncio
async def test_incremental_uses_watermarks_and_updates(tmp_path):
    db_path = tmp_path / "incremental.db"
    engine = get_engine(db_path)
    init_db(engine)
    session = get_session(engine)

    repo_id = upsert_repo(
        session,
        {
            "id": 1,
            "name": "repo",
            "full_name": "octo/repo",
            "owner": {"id": 2, "login": "octo", "type": "User"},
            "private": False,
            "default_branch": "main",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "pushed_at": "2024-01-02T00:00:00Z",
        },
    )
    session.add(
        Watermark(
            repo_id=repo_id,
            resource="issues",
            updated_at=parse_datetime("2024-01-01T00:00:00Z"),
            etag='"e-issues"',
        )
    )
    session.add(
        Watermark(
            repo_id=repo_id,
            resource="commits",
            updated_at=parse_datetime("2024-01-03T00:00:00Z"),
            etag='"e-commits"',
        )
    )
    session.add(
        Watermark(
            repo_id=repo_id,
            resource="pulls",
            updated_at=parse_datetime("2024-01-04T00:00:00Z"),
        )
    )
    session.commit()

    client = StubIncrementalClient()
    await incremental_update("octo/repo", db_path, client=client)

    issue_call = next(
        call for call in client.calls if call[0] == "/repos/octo/repo/issues"
    )
    assert issue_call[1]["since"] == "2024-01-01T00:00:00Z"
    assert issue_call[2]["If-None-Match"] == '"e-issues"'

    commit_call = next(
        call for call in client.calls if call[0] == "/repos/octo/repo/commits"
    )
    assert commit_call[1]["since"] == "2024-01-03T00:00:00Z"
    assert commit_call[2]["If-None-Match"] == '"e-commits"'

    session = get_session(engine)
    assert session.scalar(select(Issue.id)) == 100
    assert session.scalar(select(PullRequest.id)) == 200
    assert session.scalar(select(PullRequestFile.path)) == "README.md"
    assert session.scalar(select(Commit.sha)) == "c1"

    issue_wm = session.execute(
        select(Watermark).where(Watermark.resource == "issues")
    ).scalar_one()
    commit_wm = session.execute(
        select(Watermark).where(Watermark.resource == "commits")
    ).scalar_one()
    pr_wm = session.execute(
        select(Watermark).where(Watermark.resource == "pulls")
    ).scalar_one()

    assert parse_datetime(issue_wm.updated_at) == parse_datetime("2024-01-05T00:00:00Z")
    assert parse_datetime(commit_wm.updated_at) == parse_datetime(
        "2024-01-07T00:00:00Z"
    )
    assert parse_datetime(pr_wm.updated_at) == parse_datetime("2024-01-06T00:00:00Z")


@pytest.mark.asyncio
async def test_incremental_resume_skips_completed_stages(tmp_path):
    db_path = tmp_path / "incremental-resume.db"
    engine = get_engine(db_path)
    init_db(engine)
    session = get_session(engine)

    repo_id = upsert_repo(
        session,
        {
            "id": 1,
            "name": "repo",
            "full_name": "octo/repo",
            "owner": {"id": 2, "login": "octo", "type": "User"},
            "private": False,
            "default_branch": "main",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "pushed_at": "2024-01-02T00:00:00Z",
        },
    )
    for stage in (
        "repo_seed",
        "commits",
        "refs_and_releases",
        "issues",
        "pull_requests",
        "issue_activity",
        "pull_request_activity",
        "intervals_rebuilt",
        "qa_report_written",
    ):
        upsert_ingestion_checkpoint(
            session,
            repo_id=repo_id,
            flow="incremental",
            stage=stage,
            details_json="{}",
        )
    session.commit()

    client = StubIncrementalClient()
    await incremental_update("octo/repo", db_path, client=client, resume=True)

    paths = [call[0] for call in client.calls]
    assert paths == ["/repos/octo/repo"]

    session = get_session(engine)
    checkpoints = session.scalars(select(IngestionCheckpoint.stage)).all()
    assert "qa_report_written" in checkpoints
