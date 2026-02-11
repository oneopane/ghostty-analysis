from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING

from ...history.reader import HistoryReader

if TYPE_CHECKING:
    from ...inputs.models import PRInputBundle
from ..base import Evidence, RouteCandidate, RouteResult, Target, TargetType


_TEAM_RE = re.compile(
    r"(?<![A-Za-z0-9_])@(?P<org>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/(?P<team>[A-Za-z0-9][A-Za-z0-9-]*)"
)
_USER_RE = re.compile(r"(?<![A-Za-z0-9_])@(?P<user>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))")


def extract_targets(text: str) -> list[Target]:
    """Extract mentioned targets in first-appearance order."""
    hits: list[tuple[int, Target]] = []
    team_spans: list[tuple[int, int]] = []
    for m in _TEAM_RE.finditer(text):
        org = m.group("org")
        team = m.group("team")
        team_spans.append((m.start(), m.end()))
        hits.append((m.start(), Target(type=TargetType.team, name=f"{org}/{team}")))
    for m in _USER_RE.finditer(text):
        if any(s <= m.start() < e for s, e in team_spans):
            continue
        hits.append((m.start(), Target(type=TargetType.user, name=m.group("user"))))

    hits.sort(key=lambda kv: kv[0])
    seen: set[tuple[TargetType, str]] = set()
    out: list[Target] = []
    for _, target in hits:
        key = (target.type, target.name.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(target)
    return out


class MentionsRouter:
    """Baseline: route to @mentions in PR body."""

    def route(
        self,
        *,
        repo: str,
        pr_number: int,
        as_of: datetime,
        data_dir: str = "data",
        top_k: int = 5,
        input_bundle: PRInputBundle | None = None,
    ) -> RouteResult:
        with HistoryReader(repo_full_name=repo, data_dir=data_dir) as reader:
            pr = reader.pull_request_snapshot(number=pr_number, as_of=as_of)

        text = pr.body or ""
        targets = extract_targets(text)
        candidates: list[RouteCandidate] = []
        for i, t in enumerate(targets[:top_k]):
            score = 1.0 / (1.0 + i)
            candidates.append(
                RouteCandidate(
                    target=t,
                    score=score,
                    evidence=[Evidence(kind="mention", data={"source": "pr_body"})],
                )
            )

        risk = "low" if candidates else "high"
        return RouteResult(
            repo=repo,
            pr_number=pr_number,
            as_of=as_of,
            top_k=top_k,
            candidates=candidates,
            risk=risk,
        )
