from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import func, select

from ..github.client import PaginationGap
from ..storage.schema import IngestionGap
from gh.storage.upsert import insert_gap, insert_qa_report


class GapRecorder:
    def __init__(self, session, repo_id: int, resource: str):
        self.session = session
        self.repo_id = repo_id
        self.resource = resource

    def __call__(self, gap: PaginationGap) -> None:
        insert_gap(
            self.session,
            self.repo_id,
            self.resource,
            url=gap.url,
            page=gap.page,
            expected_page=gap.expected_page,
            detail=gap.detail,
        )


def write_qa_report(session, repo_id: int) -> None:
    rows = session.execute(
        select(IngestionGap.resource, func.count())
        .where(IngestionGap.repo_id == repo_id)
        .group_by(IngestionGap.resource)
    ).all()
    summary = {
        "repo_id": repo_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gap_counts": {resource: count for resource, count in rows},
        "total_gaps": sum(count for _, count in rows),
    }
    insert_qa_report(session, repo_id, json.dumps(summary))
    session.commit()
