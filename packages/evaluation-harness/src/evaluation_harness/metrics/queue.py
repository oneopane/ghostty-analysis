from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from repo_routing.router.base import RouteResult

from ..db import RepoDb, _dt_sql
from ..models import QueueMetrics, QueueRiskBucketSummary, QueueSummary


def per_pr_queue_metrics(
    *,
    result: RouteResult,
    baseline: str,
    cutoff: datetime,
    data_dir: str | Path = "data",
    include_ttfc: bool = False,
) -> QueueMetrics:
    repo = result.repo
    pr_number = result.pr_number

    db = RepoDb(repo=repo, data_dir=data_dir)
    conn = db.connect()
    try:
        repo_id = db.repo_id(conn)
        pr_id, author_id = db.pr_ids(conn, pr_number=pr_number)
        cutoff_s = _dt_sql(cutoff)

        ttfr_seconds: float | None = None
        row = conn.execute(
            """
            select r.submitted_at as submitted_at
            from reviews r
            join users u on u.id = r.user_id
            where r.repo_id = ?
              and r.pull_request_id = ?
              and r.submitted_at is not null
              and r.submitted_at >= ?
              and (u.type is null or u.type != 'Bot')
              and (? is null or r.user_id != ?)
            order by r.submitted_at asc, r.id asc
            limit 1
            """,
            (repo_id, pr_id, cutoff_s, author_id, author_id),
        ).fetchone()
        if row is not None and row["submitted_at"] is not None:
            submitted_at = datetime.fromisoformat(
                str(row["submitted_at"]).replace("Z", "+00:00")
            )
            if submitted_at.tzinfo is None:
                submitted_at = submitted_at.replace(tzinfo=timezone.utc)
            ttfr_seconds = (submitted_at - cutoff).total_seconds()

        ttfc_seconds: float | None = None
        if include_ttfc:
            row = conn.execute(
                """
                select c.created_at as created_at
                from comments c
                join users u on u.id = c.user_id
                where c.repo_id = ?
                  and c.pull_request_id = ?
                  and c.created_at is not null
                  and c.created_at >= ?
                  and (u.type is null or u.type != 'Bot')
                  and (? is null or c.user_id != ?)
                order by c.created_at asc, c.id asc
                limit 1
                """,
                (repo_id, pr_id, cutoff_s, author_id, author_id),
            ).fetchone()
            if row is not None and row["created_at"] is not None:
                created_at = datetime.fromisoformat(
                    str(row["created_at"]).replace("Z", "+00:00")
                )
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                ttfc_seconds = (created_at - cutoff).total_seconds()
    finally:
        conn.close()

    return QueueMetrics(
        repo=repo,
        pr_number=pr_number,
        cutoff=cutoff,
        ttfr_seconds=ttfr_seconds,
        ttfc_seconds=ttfc_seconds,
        risk=result.risk,
        baseline=baseline,
    )


def _mean(vals: list[float]) -> float | None:
    return None if not vals else sum(vals) / float(len(vals))


@dataclass(frozen=True)
class QueueMetricsAggregator:
    repo: str
    run_id: str
    baseline: str

    def aggregate(self, per_pr: Iterable[QueueMetrics]) -> QueueSummary:
        rows = list(per_pr)
        n = len(rows)
        if n == 0:
            return QueueSummary(
                repo=self.repo,
                run_id=self.run_id,
                baseline=self.baseline,
                n=0,
            )

        by_risk: dict[str, list[QueueMetrics]] = {}
        for r in rows:
            risk = (r.risk or "unknown").lower()
            by_risk.setdefault(risk, []).append(r)

        buckets: dict[str, QueueRiskBucketSummary] = {}
        for risk, rs in sorted(by_risk.items(), key=lambda kv: kv[0]):
            ttfr = [x.ttfr_seconds for x in rs if x.ttfr_seconds is not None]
            ttfc = [x.ttfc_seconds for x in rs if x.ttfc_seconds is not None]
            buckets[risk] = QueueRiskBucketSummary(
                n=len(rs),
                ttfr_seconds_mean=_mean([float(v) for v in ttfr]),
                ttfc_seconds_mean=_mean([float(v) for v in ttfc]),
            )

        return QueueSummary(
            repo=self.repo,
            run_id=self.run_id,
            baseline=self.baseline,
            n=n,
            by_risk=buckets,
        )
