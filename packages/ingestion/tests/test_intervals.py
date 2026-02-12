from sqlalchemy import select

from gh_history_ingestion.events.normalize import EventRecord
from gh_history_ingestion.intervals.rebuild import rebuild_intervals
from gh_history_ingestion.storage.db import get_engine, init_db, get_session
from gh_history_ingestion.storage.schema import (
    Issue,
    IssueLabelInterval,
    IssueStateInterval,
    Label,
    Repo,
)
from gh.storage.upsert import insert_event


def test_interval_rebuild_for_issue_state_and_labels(tmp_path):
    engine = get_engine(tmp_path / "intervals.db")
    init_db(engine)
    session = get_session(engine)
    session.add(Repo(id=1, owner_login="octo", name="repo", full_name="octo/repo"))
    session.add(Issue(id=10, repo_id=1, number=1, title="a", body="", is_pull_request=False))
    session.add(Label(id=5, repo_id=1, name="bug", color="f00"))
    session.commit()

    insert_event(
        session,
        EventRecord(
            repo_id=1,
            occurred_at="2024-01-01T00:00:00Z",
            actor_id=1,
            subject_type="issue",
            subject_id=10,
            event_type="issue.opened",
        ),
    )
    insert_event(
        session,
        EventRecord(
            repo_id=1,
            occurred_at="2024-01-02T00:00:00Z",
            actor_id=1,
            subject_type="issue",
            subject_id=10,
            event_type="issue.label.add",
            object_type="label",
            object_id=5,
        ),
    )
    insert_event(
        session,
        EventRecord(
            repo_id=1,
            occurred_at="2024-01-03T00:00:00Z",
            actor_id=1,
            subject_type="issue",
            subject_id=10,
            event_type="issue.label.remove",
            object_type="label",
            object_id=5,
        ),
    )
    insert_event(
        session,
        EventRecord(
            repo_id=1,
            occurred_at="2024-01-04T00:00:00Z",
            actor_id=1,
            subject_type="issue",
            subject_id=10,
            event_type="issue.closed",
        ),
    )
    session.commit()

    rebuild_intervals(session, repo_id=1)

    states = session.scalars(
        select(IssueStateInterval)
        .where(IssueStateInterval.issue_id == 10)
        .order_by(IssueStateInterval.id)
    ).all()
    labels = session.scalars(
        select(IssueLabelInterval).where(IssueLabelInterval.issue_id == 10)
    ).all()
    assert len(states) == 2
    assert states[0].state == "open"
    assert states[1].state == "closed"
    assert len(labels) == 1
    assert labels[0].label_id == 5
