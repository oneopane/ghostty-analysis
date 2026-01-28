from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from ...history.reader import HistoryReader
from ..base import Evidence, RouteCandidate, RouteResult, Target, TargetType
from .mentions import extract_targets


@dataclass(frozen=True)
class CodeownersMatch:
    pattern: str
    targets: list[Target]


def _parse_codeowners(text: str) -> list[CodeownersMatch]:
    rules: list[CodeownersMatch] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        pattern = parts[0]
        owners = " ".join(parts[1:])
        targets = extract_targets(owners)
        if targets:
            rules.append(CodeownersMatch(pattern=pattern, targets=targets))
    return rules


def _matches(pattern: str, path: str) -> bool:
    # Very small subset of CODEOWNERS semantics.
    # - Exact path
    # - Directory prefix ("dir/")
    # - Glob-ish wildcards via fnmatch
    if pattern.endswith("/"):
        return path.startswith(pattern)
    if "*" in pattern or "?" in pattern or "[" in pattern:
        return fnmatch.fnmatch(path, pattern)
    return path == pattern or path.endswith(pattern.lstrip("/"))


class CodeownersRouter:
    """Baseline: route to CODEOWNERS for changed files.

    This is optional/off by default. It is only considered "safe" if the caller
    can provide CODEOWNERS contents as-of the PR base SHA.
    """

    def __init__(
        self,
        *,
        enabled: bool = False,
        codeowners_at_base_sha: Callable[[str, str], str | None] | None = None,
        checkout_dir: str | Path | None = None,
    ) -> None:
        self.enabled = enabled
        self.codeowners_at_base_sha = codeowners_at_base_sha
        self.checkout_dir = Path(checkout_dir) if checkout_dir is not None else None

    def route(
        self,
        *,
        repo: str,
        pr_number: int,
        as_of: datetime,
        data_dir: str = "data",
        top_k: int = 5,
    ) -> RouteResult:
        if not self.enabled:
            return RouteResult(
                repo=repo,
                pr_number=pr_number,
                as_of=as_of,
                top_k=top_k,
                candidates=[],
                risk="unknown",
                notes=["codeowners baseline disabled"],
            )

        with HistoryReader(repo_full_name=repo, data_dir=data_dir) as reader:
            pr = reader.pull_request_snapshot(number=pr_number, as_of=as_of)

        base_sha = pr.base_sha
        codeowners_text: str | None = None
        risk = "leaky"
        if base_sha is not None and self.codeowners_at_base_sha is not None:
            codeowners_text = self.codeowners_at_base_sha(repo, base_sha)
            risk = "low" if codeowners_text is not None else "high"
        elif self.checkout_dir is not None:
            # Leaky: reads the checkout's current CODEOWNERS, not as-of base SHA.
            p = self.checkout_dir / "CODEOWNERS"
            if p.exists():
                codeowners_text = p.read_text(encoding="utf-8")

        if not codeowners_text:
            return RouteResult(
                repo=repo,
                pr_number=pr_number,
                as_of=as_of,
                top_k=top_k,
                candidates=[],
                risk=risk,
                notes=["CODEOWNERS not available"],
            )

        rules = _parse_codeowners(codeowners_text)
        if not rules or not pr.changed_files:
            return RouteResult(
                repo=repo,
                pr_number=pr_number,
                as_of=as_of,
                top_k=top_k,
                candidates=[],
                risk=risk,
                notes=["no rules or no changed files"],
            )

        hits: dict[tuple[TargetType, str], list[Evidence]] = {}
        for f in pr.changed_files:
            for rule in rules:
                if not _matches(rule.pattern, f.path):
                    continue
                for t in rule.targets:
                    key = (t.type, t.name)
                    hits.setdefault(key, []).append(
                        Evidence(
                            kind="codeowners",
                            data={"pattern": rule.pattern, "path": f.path},
                        )
                    )

        candidates: list[RouteCandidate] = []
        for (t_type, t_name), ev in hits.items():
            candidates.append(
                RouteCandidate(
                    target=Target(type=t_type, name=t_name),
                    score=float(len(ev)),
                    evidence=ev,
                )
            )

        candidates.sort(key=lambda c: (-c.score, c.target.name.lower()))
        return RouteResult(
            repo=repo,
            pr_number=pr_number,
            as_of=as_of,
            top_k=top_k,
            candidates=candidates[:top_k],
            risk=risk,
        )
