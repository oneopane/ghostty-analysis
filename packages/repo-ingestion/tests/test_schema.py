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
