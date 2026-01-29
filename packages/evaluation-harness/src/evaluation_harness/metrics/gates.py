from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from repo_routing.history.reader import HistoryReader
from repo_routing.parsing import parse_gate_fields

from ..db import RepoDb
from ..models import GateCorrelationSummary, GateFieldCorrelation, GateMetrics


def per_pr_gate_metrics(
    *, repo: str, pr_number: int, cutoff: datetime, data_dir: str | Path = "data"
) -> GateMetrics:
    with HistoryReader(repo_full_name=repo, data_dir=data_dir) as reader:
        pr = reader.pull_request_snapshot(number=pr_number, as_of=cutoff)

    gates = parse_gate_fields(pr.body)

    db = RepoDb(repo=repo, data_dir=data_dir)
    conn = db.connect()
    try:
        pr_id, _author_id = db.pr_ids(conn, pr_number=pr_number)
        merged = db.is_merged_as_of(conn, pr_id=pr_id, cutoff=cutoff)
    finally:
        conn.close()

    return GateMetrics(
        repo=repo,
        pr_number=pr_number,
        cutoff=cutoff,
        merged=merged,
        missing_issue=gates.missing_issue,
        missing_ai_disclosure=gates.missing_ai_disclosure,
        missing_provenance=gates.missing_provenance,
    )


def _rate_true(vals: list[bool]) -> float | None:
    return None if not vals else sum(1.0 for v in vals if v) / float(len(vals))


def _field_correlation(
    *,
    rows: list[GateMetrics],
    getter,  # type: ignore[no-untyped-def]
) -> GateFieldCorrelation | None:
    xs = [r for r in rows if getter(r) is not None and r.merged is not None]
    if not xs:
        return None

    missing = [r for r in xs if getter(r) is True]
    present = [r for r in xs if getter(r) is False]

    def merged_rate(rs: list[GateMetrics]) -> float | None:
        if not rs:
            return None
        return sum(1.0 for r in rs if bool(r.merged)) / float(len(rs))

    n = len(xs)
    missing_n = len(missing)
    present_n = len(present)
    missing_rate = _rate_true([bool(getter(r)) for r in xs])
    return GateFieldCorrelation(
        n=n,
        missing_n=missing_n,
        present_n=present_n,
        missing_rate=missing_rate,
        merged_rate_missing=merged_rate(missing),
        merged_rate_present=merged_rate(present),
    )


@dataclass(frozen=True)
class GateCorrelation:
    repo: str
    run_id: str

    def aggregate(self, per_pr: Iterable[GateMetrics]) -> GateCorrelationSummary:
        rows = list(per_pr)
        n = len(rows)
        if n == 0:
            return GateCorrelationSummary(repo=self.repo, run_id=self.run_id, n=0)

        return GateCorrelationSummary(
            repo=self.repo,
            run_id=self.run_id,
            n=n,
            issue=_field_correlation(rows=rows, getter=lambda r: r.missing_issue),
            ai_disclosure=_field_correlation(
                rows=rows, getter=lambda r: r.missing_ai_disclosure
            ),
            provenance=_field_correlation(
                rows=rows, getter=lambda r: r.missing_provenance
            ),
        )
