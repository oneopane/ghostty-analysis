from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from ...inputs.models import PRInputBundle

from ...history.reader import HistoryReader
from ...paths import repo_artifact_path, repo_codeowners_path
from ...repo_profile.storage import CODEOWNERS_PATH_CANDIDATES
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


def _target_from_profile_node(node: dict[str, object]) -> Target | None:
    kind = str(node.get("kind") or "").lower()
    name = str(node.get("name") or "").strip()
    if not name:
        return None
    if kind == "team":
        return Target(type=TargetType.team, name=name)
    if kind in {"person", "alias", "unknown"}:
        return Target(type=TargetType.user, name=name)
    return None


def _rules_from_repo_profile(profile_path: str | Path) -> list[CodeownersMatch] | None:
    p = Path(profile_path)
    if not p.exists():
        return None

    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None

    graph = raw.get("ownership_graph")
    if not isinstance(graph, dict):
        return None
    nodes_raw = graph.get("nodes")
    edges_raw = graph.get("edges")
    if not isinstance(nodes_raw, list) or not isinstance(edges_raw, list):
        return None

    nodes: dict[str, Target] = {}
    for item in nodes_raw:
        if not isinstance(item, dict):
            continue
        node_id = str(item.get("node_id") or "").strip()
        if not node_id:
            continue
        target = _target_from_profile_node(item)
        if target is None:
            continue
        nodes[node_id] = target

    by_pattern: dict[str, dict[tuple[TargetType, str], Target]] = {}
    for item in edges_raw:
        if not isinstance(item, dict):
            continue
        relation = str(item.get("relation") or "").upper()
        if relation != "OWNS":
            continue

        pattern = str(item.get("path_glob") or "").strip()
        source_node_id = str(item.get("source_node_id") or "").strip()
        if not pattern or not source_node_id:
            continue

        target = nodes.get(source_node_id)
        if target is None:
            continue

        bucket = by_pattern.setdefault(pattern, {})
        bucket[(target.type, target.name.lower())] = target

    if not by_pattern:
        return None

    out: list[CodeownersMatch] = []
    for pattern in sorted(by_pattern, key=str.lower):
        targets = [
            by_pattern[pattern][k]
            for k in sorted(by_pattern[pattern], key=lambda kv: (kv[0].value, kv[1]))
        ]
        out.append(CodeownersMatch(pattern=pattern, targets=targets))
    return out


class CodeownersRouter:
    """Baseline: route to CODEOWNERS for changed files.

    This is optional/off by default. It is only considered "safe" if the caller
    can provide CODEOWNERS contents as-of the PR base SHA.
    """

    def __init__(
        self,
        *,
        enabled: bool = False,
        codeowners_at_base_sha: Callable[[str, str, str | Path], str | None]
        | None = None,
        codeowners_dir: str | Path | None = None,
    ) -> None:
        self.enabled = enabled
        self.codeowners_at_base_sha = codeowners_at_base_sha
        self.codeowners_dir = (
            Path(codeowners_dir) if codeowners_dir is not None else None
        )

    @staticmethod
    def default_codeowners_at_base_sha(
        repo: str, base_sha: str, data_dir: str | Path
    ) -> str | None:
        for rel in CODEOWNERS_PATH_CANDIDATES:
            p = repo_artifact_path(
                repo_full_name=repo,
                base_sha=base_sha,
                relative_path=rel,
                data_dir=data_dir,
            )
            if p.exists():
                return p.read_text(encoding="utf-8")
        p = repo_codeowners_path(
            repo_full_name=repo, base_sha=base_sha, data_dir=data_dir
        )
        if not p.exists():
            return None
        return p.read_text(encoding="utf-8")

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
        if not self.enabled:
            return RouteResult(
                repo=repo,
                pr_number=pr_number,
                as_of=as_of,
                top_k=top_k,
                candidates=[],
                risk="unknown",
                notes=["codeowners router disabled"],
            )

        if input_bundle is not None:
            pr = input_bundle.snapshot
            changed_files = list(input_bundle.changed_files or pr.changed_files)
        else:
            with HistoryReader(repo_full_name=repo, data_dir=data_dir) as reader:
                pr = reader.pull_request_snapshot(number=pr_number, as_of=as_of)
            changed_files = list(pr.changed_files)

        notes: list[str] = []
        rules: list[CodeownersMatch] | None = None
        risk = "high"

        if input_bundle is not None and input_bundle.repo_profile_path:
            rules = _rules_from_repo_profile(input_bundle.repo_profile_path)
            if rules is not None:
                risk = "low"
                notes.append("source=repo_profile")
            else:
                notes.append("repo_profile unavailable or invalid; falling back to CODEOWNERS")

        if rules is None:
            base_sha = pr.base_sha
            if base_sha is None:
                return RouteResult(
                    repo=repo,
                    pr_number=pr_number,
                    as_of=as_of,
                    top_k=top_k,
                    candidates=[],
                    risk=risk,
                    notes=[*notes, "missing base_sha; cannot load CODEOWNERS as-of base"],
                )

            provider = self.codeowners_at_base_sha or self.default_codeowners_at_base_sha
            co_data_dir: str | Path = (
                self.codeowners_dir if self.codeowners_dir is not None else data_dir
            )
            codeowners_text = provider(repo, base_sha, co_data_dir)
            risk = "low" if codeowners_text is not None else "high"

            if not codeowners_text:
                return RouteResult(
                    repo=repo,
                    pr_number=pr_number,
                    as_of=as_of,
                    top_k=top_k,
                    candidates=[],
                    risk=risk,
                    notes=[*notes, "CODEOWNERS not available"],
                )

            rules = _parse_codeowners(codeowners_text)
            notes.append("source=codeowners")

        if not rules or not changed_files:
            return RouteResult(
                repo=repo,
                pr_number=pr_number,
                as_of=as_of,
                top_k=top_k,
                candidates=[],
                risk=risk,
                notes=[*notes, "no rules or no changed files"],
            )

        hits: dict[tuple[TargetType, str], list[Evidence]] = {}
        for f in changed_files:
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
            notes=notes,
        )
