from __future__ import annotations

import sqlite3
from datetime import timedelta

from evaluation_harness.models import TruthStatus
from evaluation_harness.truth import behavior_truth_with_diagnostics

from .fixtures.build_min_db import build_min_db


def test_truth_diagnostics_observed_when_response_found(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)

    diag = behavior_truth_with_diagnostics(
        repo=db.repo,
        pr_number=db.pr_number,
        cutoff=db.created_at,
        data_dir=db.data_dir,
        window=timedelta(hours=2),
    )

    assert diag.status == TruthStatus.observed
    assert diag.selected_login == db.reviewer_login
    assert diag.selected_source == "review_comment"
    assert diag.include_review_comments is True


def test_truth_diagnostics_no_response_when_coverage_complete(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)

    diag = behavior_truth_with_diagnostics(
        repo=db.repo,
        pr_number=db.pr_number,
        cutoff=db.created_at + timedelta(minutes=20),
        data_dir=db.data_dir,
        window=timedelta(minutes=10),
        include_review_comments=False,
    )

    assert diag.status == TruthStatus.no_post_cutoff_response
    assert diag.coverage_complete is True
    assert diag.selected_login is None


def test_truth_diagnostics_can_exclude_review_comments(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)

    diag = behavior_truth_with_diagnostics(
        repo=db.repo,
        pr_number=db.pr_number,
        cutoff=db.created_at,
        data_dir=db.data_dir,
        window=timedelta(hours=2),
        include_review_comments=False,
    )

    assert diag.status == TruthStatus.observed
    assert diag.selected_login == db.reviewer_login
    assert diag.selected_source == "review_submitted"
    assert diag.scanned_review_rows == 1
    assert diag.scanned_review_comment_rows == 0


def test_truth_diagnostics_unknown_when_truth_related_gap_exists(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)

    conn = sqlite3.connect(str(db.db_path))
    try:
        conn.execute(
            """
            create table ingestion_gaps (
                id integer primary key,
                repo_id integer,
                resource text,
                url text,
                page integer,
                expected_page integer,
                detail text,
                detected_at text
            )
            """
        )
        conn.execute(
            "insert into ingestion_gaps (repo_id, resource, detail) values (1, 'reviews', 'test gap')"
        )
        conn.commit()
    finally:
        conn.close()

    diag = behavior_truth_with_diagnostics(
        repo=db.repo,
        pr_number=db.pr_number,
        cutoff=db.created_at + timedelta(minutes=20),
        data_dir=db.data_dir,
        window=timedelta(minutes=10),
        include_review_comments=False,
    )

    assert diag.status == TruthStatus.unknown_due_to_ingestion_gap
    assert "reviews" in diag.gap_resources
