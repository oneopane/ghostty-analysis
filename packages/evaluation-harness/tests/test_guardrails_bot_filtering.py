from __future__ import annotations

import sqlite3
from datetime import datetime

from evaluation_harness.truth import behavior_truth_first_eligible_review

from .fixtures.build_min_db import build_min_db


def test_behavior_truth_ignores_bots(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)

    conn = sqlite3.connect(str(db.db_path))
    try:
        conn.execute(
            "insert into users (id, login, type) values (?, ?, ?)",
            (12, "robot[bot]", "Bot"),
        )
        conn.execute(
            "insert into reviews (id, repo_id, pull_request_id, user_id, submitted_at) values (?, ?, ?, ?, ?)",
            (
                501,
                1,
                100,
                12,
                datetime.fromisoformat("2024-01-01T00:10:00+00:00")
                .replace(tzinfo=None)
                .isoformat(sep=" "),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    truth = behavior_truth_first_eligible_review(
        repo=db.repo,
        pr_number=db.pr_number,
        cutoff=datetime.fromisoformat("2024-01-01T00:00:00+00:00"),
        data_dir=db.data_dir,
        exclude_author=True,
        exclude_bots=True,
    )
    assert truth == "bob"


def test_behavior_truth_requires_post_cutoff_response(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)

    truth = behavior_truth_first_eligible_review(
        repo=db.repo,
        pr_number=db.pr_number,
        cutoff=datetime.fromisoformat("2024-01-02T00:00:00+00:00"),
        data_dir=db.data_dir,
        exclude_author=True,
        exclude_bots=True,
    )
    assert truth is None
