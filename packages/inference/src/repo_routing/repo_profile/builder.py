from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Sequence

from ..time import require_dt_utc
from .models import (
    BoundaryEntry,
    BoundaryModel,
    OwnershipEdge,
    OwnershipGraph,
    OwnershipNode,
    PolicySignal,
    PolicySignals,
    ProvenanceEntry,
    RepoArtifactEntry,
    RepoArtifactManifest,
    RepoProfile,
    RepoProfileBuildResult,
    RepoProfileCoverage,
    RepoProfileIdentity,
    RepoProfileQAReport,
    RepoVocabulary,
    VocabularyEntry,
)
from .parsers.codeowners import boundary_for_pattern, parse_codeowners_rules
from .storage import (
    CODEOWNERS_PATH_CANDIDATES,
    DEFAULT_PINNED_ARTIFACT_PATHS,
    detect_type,
    normalize_relpath,
    normalize_text,
    pinned_artifact_path,
    stable_sha256_text,
)


def _read_text(path: Path) -> str:
    return normalize_text(path.read_text(encoding="utf-8", errors="replace"))


def _first_existing(
    *,
    repo: str,
    base_sha: str,
    candidates: Sequence[str],
    data_dir: str | Path,
) -> tuple[str, str] | None:
    for rel in candidates:
        p = pinned_artifact_path(
            repo_full_name=repo,
            base_sha=base_sha,
            relative_path=rel,
            data_dir=data_dir,
        )
        if p.exists():
            return normalize_relpath(rel), _read_text(p)
    return None


def _build_policy_signals(
    *,
    contributing_path: str | None,
    contributing_text: str | None,
    codeowners_present: bool,
) -> PolicySignals:
    source = contributing_path or "__unknown__"
    text = (contributing_text or "").lower()
    signals = [
        PolicySignal(
            key="codeowners_present",
            value="yes" if codeowners_present else "no",
            provenance=[ProvenanceEntry(path=source, note="derived signal")],
        ),
        PolicySignal(
            key="issue_reference_policy",
            value="mentioned" if "issue" in text else "unknown",
            provenance=[ProvenanceEntry(path=source)],
        ),
        PolicySignal(
            key="ai_disclosure_policy",
            value=(
                "mentioned"
                if ("ai" in text and "disclosure" in text)
                else "unknown"
            ),
            provenance=[ProvenanceEntry(path=source)],
        ),
        PolicySignal(
            key="provenance_policy",
            value="mentioned" if "provenance" in text else "unknown",
            provenance=[ProvenanceEntry(path=source)],
        ),
    ]
    signals.sort(key=lambda s: s.key)
    return PolicySignals(signals=signals)


def _build_vocabulary(
    *,
    contributing_path: str | None,
    contributing_text: str | None,
) -> RepoVocabulary:
    source = contributing_path or "__unknown__"
    text = (contributing_text or "").lower()

    keywords: list[VocabularyEntry] = []
    if "issue" in text:
        keywords.append(
            VocabularyEntry(
                token="issue",
                canonical_intent="link_issue",
                gate="issue",
                provenance=[ProvenanceEntry(path=source)],
            )
        )
    if "ai" in text and "disclosure" in text:
        keywords.append(
            VocabularyEntry(
                token="ai disclosure",
                canonical_intent="disclose_ai_usage",
                gate="ai_disclosure",
                provenance=[ProvenanceEntry(path=source)],
            )
        )
    if "provenance" in text:
        keywords.append(
            VocabularyEntry(
                token="provenance",
                canonical_intent="supply_provenance",
                gate="provenance",
                provenance=[ProvenanceEntry(path=source)],
            )
        )

    keywords.sort(key=lambda e: e.token)
    return RepoVocabulary(keywords=keywords)


def build_repo_profile(
    *,
    repo: str,
    pr_number: int,
    cutoff: datetime,
    base_sha: str,
    data_dir: str | Path = "data",
    artifact_paths: Sequence[str] | None = None,
    critical_artifact_paths: Sequence[str] | None = None,
) -> RepoProfileBuildResult:
    owner, repo_name = repo.split("/", 1)
    cutoff_utc = require_dt_utc(cutoff, name="cutoff")

    requested_paths = artifact_paths or DEFAULT_PINNED_ARTIFACT_PATHS
    requested_norm = sorted(
        {normalize_relpath(p) for p in requested_paths},
        key=str.lower,
    )
    critical_norm = sorted(
        {normalize_relpath(p) for p in (critical_artifact_paths or ())},
        key=str.lower,
    )

    manifest_entries: list[RepoArtifactEntry] = []
    existing_paths: set[str] = set()
    for rel in requested_norm:
        p = pinned_artifact_path(
            repo_full_name=repo,
            base_sha=base_sha,
            relative_path=rel,
            data_dir=data_dir,
        )
        if not p.exists():
            continue
        text = _read_text(p)
        existing_paths.add(rel)
        manifest_entries.append(
            RepoArtifactEntry(
                path=rel,
                content_sha256=stable_sha256_text(text),
                size_bytes=len(text.encode("utf-8")),
                detected_type=detect_type(rel),
            )
        )

    manifest_entries.sort(key=lambda e: e.path.lower())
    artifact_manifest = RepoArtifactManifest(files=manifest_entries)

    codeowners = _first_existing(
        repo=repo,
        base_sha=base_sha,
        candidates=CODEOWNERS_PATH_CANDIDATES,
        data_dir=data_dir,
    )
    codeowners_path = None if codeowners is None else codeowners[0]
    codeowners_text = None if codeowners is None else codeowners[1]

    contributing = _first_existing(
        repo=repo,
        base_sha=base_sha,
        candidates=("CONTRIBUTING.md", ".github/CONTRIBUTING.md"),
        data_dir=data_dir,
    )
    contributing_path = None if contributing is None else contributing[0]
    contributing_text = None if contributing is None else contributing[1]

    rules = parse_codeowners_rules(codeowners_text or "")

    nodes: dict[str, OwnershipNode] = {}
    edges: list[OwnershipEdge] = []
    boundary_map: dict[str, set[str]] = {}
    for rule in rules:
        boundary = boundary_for_pattern(rule.pattern)
        boundary_map.setdefault(boundary, set()).add(rule.pattern)
        for owner_entry in rule.owners:
            node_id = owner_entry.canonical_id
            if node_id not in nodes:
                nodes[node_id] = OwnershipNode(
                    node_id=node_id,
                    kind=owner_entry.kind,  # type: ignore[arg-type]
                    name=owner_entry.name,
                    provenance=[
                        ProvenanceEntry(path=codeowners_path or "__unknown__", line=rule.line)
                    ],
                    confidence=1.0,
                )
            edges.append(
                OwnershipEdge(
                    relation="OWNS",
                    source_node_id=node_id,
                    path_glob=rule.pattern,
                    boundary=boundary,
                    provenance=[
                        ProvenanceEntry(path=codeowners_path or "__unknown__", line=rule.line)
                    ],
                    confidence=1.0,
                )
            )

    graph = OwnershipGraph(
        nodes=sorted(nodes.values(), key=lambda n: n.node_id.lower()),
        edges=sorted(
            edges,
            key=lambda e: (
                e.source_node_id.lower(),
                (e.path_glob or "").lower(),
                (e.boundary or "").lower(),
            ),
        ),
    )

    boundaries: list[BoundaryEntry] = []
    for boundary, globs in boundary_map.items():
        boundaries.append(
            BoundaryEntry(
                boundary=boundary,
                path_globs=sorted(globs, key=str.lower),
                provenance=[ProvenanceEntry(path=codeowners_path or "__unknown__")],
            )
        )
    if not boundaries:
        boundaries.append(
            BoundaryEntry(
                boundary="__unknown__",
                path_globs=[],
                provenance=[ProvenanceEntry(path="__unknown__", note="no codeowners")],
            )
        )
    boundaries.sort(key=lambda b: b.boundary.lower())
    boundary_model = BoundaryModel(boundaries=boundaries)

    policy_signals = _build_policy_signals(
        contributing_path=contributing_path,
        contributing_text=contributing_text,
        codeowners_present=codeowners_text is not None,
    )
    vocabulary = _build_vocabulary(
        contributing_path=contributing_path,
        contributing_text=contributing_text,
    )

    present_critical = [p for p in critical_norm if p in existing_paths]
    missing_critical = [p for p in critical_norm if p not in existing_paths]
    confidence_distribution = {
        "high": len(graph.nodes) + len(graph.edges),
        "medium": 0,
        "low": 0,
    }
    warnings: list[str] = []
    if codeowners_text is None:
        warnings.append("CODEOWNERS not found in pinned artifacts")
    if not graph.nodes:
        warnings.append("ownership graph is empty")
    if missing_critical:
        warnings.append(
            "missing critical artifacts: " + ", ".join(sorted(missing_critical))
        )

    identity = RepoProfileIdentity(
        owner=owner,
        repo=repo_name,
        pr_number=pr_number,
        cutoff=cutoff_utc,
        base_sha=base_sha,
    )
    coverage = RepoProfileCoverage(
        artifact_count=len(artifact_manifest.files),
        codeowners_present=codeowners_text is not None,
        critical_artifacts=critical_norm,
        present_critical_artifacts=present_critical,
        missing_critical_artifacts=missing_critical,
    )
    qa = RepoProfileQAReport(
        identity=identity,
        coverage=coverage,
        confidence_distribution=confidence_distribution,
        warnings=warnings,
    )

    profile = RepoProfile(
        identity=identity,
        artifact_manifest=artifact_manifest,
        ownership_graph=graph,
        boundary_model=boundary_model,
        policy_signals=policy_signals,
        vocabulary=vocabulary,
    )
    return RepoProfileBuildResult(profile=profile, qa_report=qa)
