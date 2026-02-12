from gh_history_ingestion.events.normalize import (
    normalize_issue_event,
    normalize_issue_opened,
)


def test_normalize_issue_opened_event():
    issue = {
        "id": 100,
        "number": 1,
        "title": "Fix",
        "body": "Details",
        "state": "open",
        "created_at": "2024-01-01T00:00:00Z",
        "user": {"id": 42, "login": "alice"},
    }
    events = normalize_issue_opened(issue, repo_id=9)
    assert events[0].event_type == "issue.opened"
    assert events[0].subject_type == "issue"
    assert events[0].subject_id == 100


def test_normalize_issue_label_event():
    payload = {
        "id": 1,
        "event": "labeled",
        "created_at": "2024-01-02T00:00:00Z",
        "actor": {"id": 7, "login": "bob"},
        "label": {"id": 55, "name": "bug", "color": "f00"},
    }
    events = normalize_issue_event(issue_id=100, repo_id=9, payload=payload)
    assert events[0].event_type == "issue.label.add"
    assert events[0].object_type == "label"
    assert events[0].object_id == 55


def test_normalize_review_request_event_targets_pr():
    payload = {
        "id": 2,
        "event": "review_requested",
        "created_at": "2024-01-03T00:00:00Z",
        "actor": {"id": 7, "login": "bob"},
        "requested_reviewer": {"id": 88, "login": "carol"},
    }
    events = normalize_issue_event(
        issue_id=100,
        repo_id=9,
        payload=payload,
        pull_request_id=200,
    )
    assert events[0].event_type == "pull_request.review_request.add"
    assert events[0].subject_type == "pull_request"
    assert events[0].subject_id == 200


def test_normalize_unknown_event_is_captured():
    payload = {
        "id": 10,
        "event": "some_custom",
        "created_at": "2024-01-05T00:00:00Z",
        "actor": {"id": 7, "login": "bob"},
    }
    events = normalize_issue_event(issue_id=100, repo_id=9, payload=payload)
    assert events[0].event_type == "issue.event.some_custom"


def test_normalize_edited_without_content_keeps_payload():
    payload = {
        "id": 11,
        "event": "edited",
        "created_at": "2024-01-05T00:00:00Z",
        "actor": {"id": 7, "login": "bob"},
        "changes": {"title": {"from": "old"}},
    }
    events = normalize_issue_event(issue_id=100, repo_id=9, payload=payload)
    assert events[0].event_type == "issue.edited"


def test_normalize_review_dismissed_on_pr():
    payload = {
        "id": 12,
        "event": "review_dismissed",
        "created_at": "2024-01-05T00:00:00Z",
        "actor": {"id": 7, "login": "bob"},
        "dismissed_review": {"review_id": 700},
    }
    events = normalize_issue_event(
        issue_id=100, repo_id=9, payload=payload, pull_request_id=200
    )
    assert events[0].event_type == "review.dismissed"
    assert events[0].object_type == "review"
    assert events[0].object_id == 700


def test_normalize_merged_event_on_pr():
    payload = {
        "id": 13,
        "event": "merged",
        "created_at": "2024-01-06T00:00:00Z",
        "actor": {"id": 7, "login": "bob"},
        "commit_id": "deadbeef",
    }
    events = normalize_issue_event(
        issue_id=100, repo_id=9, payload=payload, pull_request_id=200
    )
    assert events[0].event_type == "pull_request.merged"
    assert events[0].commit_sha == "deadbeef"
