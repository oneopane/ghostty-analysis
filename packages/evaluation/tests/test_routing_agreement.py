from __future__ import annotations

from datetime import datetime, timezone

from evaluation_harness.metrics.routing_agreement import per_pr_metrics
from evaluation_harness.models import TruthLabel
from repo_routing.router.base import RouteCandidate, RouteResult, Target, TargetType


def test_routing_agreement_hit_and_mrr() -> None:
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    result = RouteResult(
        repo="acme/widgets",
        pr_number=1,
        as_of=now,
        candidates=[
            RouteCandidate(target=Target(type=TargetType.user, name="a"), score=1.0),
            RouteCandidate(target=Target(type=TargetType.user, name="b"), score=0.5),
            RouteCandidate(target=Target(type=TargetType.user, name="c"), score=0.2),
        ],
    )
    truth = TruthLabel(
        repo=result.repo, pr_number=result.pr_number, cutoff=now, targets=["b"]
    )
    m = per_pr_metrics(result=result, truth=truth)
    assert m.hit_at_1 == 0.0
    assert m.hit_at_3 == 1.0
    assert m.hit_at_5 == 1.0
    assert m.mrr == 0.5
