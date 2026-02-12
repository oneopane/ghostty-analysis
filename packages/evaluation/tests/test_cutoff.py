from __future__ import annotations

from datetime import timedelta

from evaluation_harness.cutoff import cutoff_for_pr

from .fixtures.build_min_db import build_min_db


def test_cutoff_created_at(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)
    cutoff = cutoff_for_pr(repo=db.repo, pr_number=db.pr_number, data_dir=db.data_dir)
    assert cutoff == db.created_at


def test_cutoff_created_at_plus_delta(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)
    cutoff = cutoff_for_pr(
        repo=db.repo,
        pr_number=db.pr_number,
        data_dir=db.data_dir,
        policy="created_at+60m",
    )
    assert cutoff == db.created_at + timedelta(minutes=60)


def test_cutoff_ready_for_review(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path, draft_at_open=True)
    cutoff = cutoff_for_pr(
        repo=db.repo,
        pr_number=db.pr_number,
        data_dir=db.data_dir,
        policy="ready_for_review",
    )
    # build_min_db defaults ready_for_review_at to created_at + 10 minutes
    assert cutoff == db.created_at + timedelta(minutes=10)
