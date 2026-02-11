from sqlalchemy import select

from gh_history_ingestion.storage.db import get_engine, get_session, init_db
from gh_history_ingestion.storage.schema import PullRequestFile
from gh_history_ingestion.storage.upsert import (
    upsert_pull_request,
    upsert_pull_request_file,
    upsert_repo,
    upsert_user,
)


def test_pull_request_files_upsert_is_idempotent(tmp_path):
    db_path = tmp_path / "pr-files.db"
    engine = get_engine(db_path)
    init_db(engine)
    session = get_session(engine)

    upsert_user(session, {"id": 2, "login": "octo", "type": "User"})
    repo_id = upsert_repo(
        session,
        {
            "id": 1,
            "name": "repo",
            "full_name": "octo/repo",
            "owner": {"id": 2, "login": "octo", "type": "User"},
            "private": False,
            "default_branch": "main",
        },
    )
    pr_id = upsert_pull_request(
        session,
        repo_id,
        {
            "id": 200,
            "number": 1,
            "title": "PR",
            "head": {"sha": "abc"},
            "base": {"sha": "def"},
        },
        issue_id=None,
    )
    session.commit()

    upsert_pull_request_file(
        session,
        repo_id,
        pr_id,
        head_sha="abc",
        file={"filename": "README.md", "status": "modified", "additions": 1},
    )
    upsert_pull_request_file(
        session,
        repo_id,
        pr_id,
        head_sha="abc",
        file={"filename": "README.md", "status": "modified", "additions": 2},
    )
    session.commit()

    row = session.execute(
        select(PullRequestFile).where(
            PullRequestFile.repo_id == repo_id,
            PullRequestFile.pull_request_id == pr_id,
            PullRequestFile.head_sha == "abc",
            PullRequestFile.path == "README.md",
        )
    ).scalar_one()
    assert row.additions == 2


def test_pull_request_files_are_versioned_by_pr_head_sha(tmp_path):
    db_path = tmp_path / "pr-files-heads.db"
    engine = get_engine(db_path)
    init_db(engine)
    session = get_session(engine)

    upsert_user(session, {"id": 2, "login": "octo", "type": "User"})
    repo_id = upsert_repo(
        session,
        {
            "id": 1,
            "name": "repo",
            "full_name": "octo/repo",
            "owner": {"id": 2, "login": "octo", "type": "User"},
            "private": False,
            "default_branch": "main",
        },
    )
    pr_id = upsert_pull_request(
        session,
        repo_id,
        {
            "id": 200,
            "number": 1,
            "title": "PR",
            "head": {"sha": "abc"},
            "base": {"sha": "def"},
        },
        issue_id=None,
    )

    # First snapshot at head=abc.
    upsert_pull_request_file(
        session,
        repo_id,
        pr_id,
        head_sha="abc",
        file={"filename": "README.md", "status": "modified", "changes": 1},
    )

    # Later snapshot at head=def should coexist, not overwrite abc rows.
    upsert_pull_request(
        session,
        repo_id,
        {
            "id": 200,
            "number": 1,
            "title": "PR",
            "head": {"sha": "def"},
            "base": {"sha": "def"},
        },
        issue_id=None,
    )
    upsert_pull_request_file(
        session,
        repo_id,
        pr_id,
        head_sha="def",
        file={"filename": "README.md", "status": "modified", "changes": 2},
    )
    session.commit()

    rows = (
        session.execute(
            select(PullRequestFile)
            .where(
                PullRequestFile.repo_id == repo_id,
                PullRequestFile.pull_request_id == pr_id,
                PullRequestFile.path == "README.md",
            )
            .order_by(PullRequestFile.head_sha.asc())
        )
        .scalars()
        .all()
    )

    assert [r.head_sha for r in rows] == ["abc", "def"]
    assert [r.changes for r in rows] == [1, 2]
