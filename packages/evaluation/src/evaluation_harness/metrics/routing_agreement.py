from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from repo_routing.router.base import RouteResult

from ..models import PRMetrics, RoutingAgreementSummary, TruthLabel


def _rank_of_truth(*, result: RouteResult, truth_targets: set[str]) -> int | None:
    for i, c in enumerate(result.candidates, start=1):
        if c.target.name in truth_targets:
            return i
    return None


def per_pr_metrics(*, result: RouteResult, truth: TruthLabel) -> PRMetrics:
    truth_targets = set(truth.targets)
    rank = _rank_of_truth(result=result, truth_targets=truth_targets)

    hit1 = 1.0 if (rank is not None and rank <= 1) else 0.0
    hit3 = 1.0 if (rank is not None and rank <= 3) else 0.0
    hit5 = 1.0 if (rank is not None and rank <= 5) else 0.0
    mrr = 0.0 if rank is None else 1.0 / float(rank)

    return PRMetrics(
        repo=result.repo,
        pr_number=result.pr_number,
        cutoff=truth.cutoff,
        hit_at_1=hit1,
        hit_at_3=hit3,
        hit_at_5=hit5,
        mrr=mrr,
    )


@dataclass(frozen=True)
class RoutingAgreement:
    repo: str
    run_id: str

    def aggregate(self, per_pr: Iterable[PRMetrics]) -> RoutingAgreementSummary:
        rows = list(per_pr)
        n = len(rows)
        if n == 0:
            return RoutingAgreementSummary(repo=self.repo, run_id=self.run_id, n=0)

        def mean(vals: list[float | None]) -> float | None:
            xs = [v for v in vals if v is not None]
            return None if not xs else sum(xs) / float(len(xs))

        return RoutingAgreementSummary(
            repo=self.repo,
            run_id=self.run_id,
            n=n,
            hit_at_1=mean([r.hit_at_1 for r in rows]),
            hit_at_3=mean([r.hit_at_3 for r in rows]),
            hit_at_5=mean([r.hit_at_5 for r in rows]),
            mrr=mean([r.mrr for r in rows]),
        )
