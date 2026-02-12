from sqlalchemy import inspect

from gh_history_ingestion.storage.db import get_engine, init_db


def test_schema_creation(tmp_path):
    db_path = tmp_path / "schema.db"
    engine = get_engine(db_path)
    init_db(engine)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    expected = {
        "repos",
        "users",
        "teams",
        "labels",
        "milestones",
        "commits",
        "refs",
        "releases",
        "watermarks",
        "ingestion_gaps",
        "qa_reports",
        "issues",
        "pull_requests",
        "pull_request_files",
        "reviews",
        "comments",
        "events",
        "issue_state_intervals",
        "issue_content_intervals",
        "issue_label_intervals",
        "issue_assignee_intervals",
        "issue_milestone_intervals",
        "pull_request_draft_intervals",
        "pull_request_head_intervals",
        "pull_request_review_request_intervals",
        "comment_content_intervals",
        "review_content_intervals",
        "object_snapshots",
    }
    assert expected.issubset(tables)


def test_pull_request_files_indexes_exist(tmp_path):
    db_path = tmp_path / "schema-indexes.db"
    engine = get_engine(db_path)
    init_db(engine)
    inspector = inspect(engine)

    index_names = {idx["name"] for idx in inspector.get_indexes("pull_request_files")}
    assert "ix_pr_files_repo_pr_head" in index_names
    assert "ix_pr_files_repo_path" in index_names
