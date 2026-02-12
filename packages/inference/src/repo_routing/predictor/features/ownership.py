from __future__ import annotations

import fnmatch
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...exports.area import default_area_for_path, load_repo_area_overrides
from ...inputs.models import PRInputBundle
from ...paths import repo_artifact_path, repo_codeowners_path
from ...repo_profile.storage import CODEOWNERS_PATH_CANDIDATES
from ...router.baselines.codeowners import CodeownersMatch
from ...router.baselines.mentions import extract_targets


@dataclass(frozen=True)
class OwnershipMatchSummary:
    owner_set: set[str]
    owner_by_file: dict[str, set[str]]
    files_with_owner: int
    total_files: int


def load_codeowners_text(
    *,
    repo: str,
    base_sha: str | None,
    data_dir: str | Path,
) -> str | None:
    if not base_sha:
        return None
    for rel in CODEOWNERS_PATH_CANDIDATES:
        p = repo_artifact_path(
            repo_full_name=repo,
            base_sha=base_sha,
            relative_path=rel,
            data_dir=data_dir,
        )
        if p.exists():
            return p.read_text(encoding="utf-8")

    # Backward-compatible fallback for older artifact layout.
    p_legacy = repo_codeowners_path(
        repo_full_name=repo,
        base_sha=base_sha,
        data_dir=data_dir,
    )
    if p_legacy.exists():
        return p_legacy.read_text(encoding="utf-8")
    return None


def load_codeowners_text_for_pr(*, input: PRInputBundle, data_dir: str | Path) -> str | None:
    return load_codeowners_text(
        repo=input.repo,
        base_sha=input.snapshot.base_sha,
        data_dir=data_dir,
    )


def parse_codeowners_rules(codeowners_text: str) -> list[CodeownersMatch]:
    rules: list[CodeownersMatch] = []
    for raw in codeowners_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        pattern = parts[0]
        owners = " ".join(parts[1:])
        targets = extract_targets(owners)
        if not targets:
            continue
        rules.append(CodeownersMatch(pattern=pattern, targets=targets))
    return rules


def _matches(pattern: str, path: str) -> bool:
    if pattern.endswith("/"):
        return path.startswith(pattern)
    if "*" in pattern or "?" in pattern or "[" in pattern:
        return fnmatch.fnmatch(path, pattern)
    return path == pattern or path.endswith(pattern.lstrip("/"))


def match_codeowners_for_changed_files(
    input: PRInputBundle,
    *,
    rules: list[CodeownersMatch],
) -> OwnershipMatchSummary:
    owner_by_file: dict[str, set[str]] = {}
    for f in sorted(input.changed_files, key=lambda x: x.path):
        owners: set[str] = set()
        for rule in rules:
            if not _matches(rule.pattern, f.path):
                continue
            for t in rule.targets:
                owners.add(t.name)
        owner_by_file[f.path] = owners

    owner_set = set().union(*owner_by_file.values()) if owner_by_file else set()
    files_with_owner = sum(1 for owners in owner_by_file.values() if owners)
    return OwnershipMatchSummary(
        owner_set=owner_set,
        owner_by_file=owner_by_file,
        files_with_owner=files_with_owner,
        total_files=len(input.changed_files),
    )


def owner_set_size(summary: OwnershipMatchSummary) -> int:
    return len(summary.owner_set)


def owner_coverage_ratio(summary: OwnershipMatchSummary) -> float:
    if summary.total_files <= 0:
        return 0.0
    return float(summary.files_with_owner) / float(summary.total_files)


def max_owners_on_any_file(summary: OwnershipMatchSummary) -> int:
    if not summary.owner_by_file:
        return 0
    return max(len(x) for x in summary.owner_by_file.values())


def top_owner_share(summary: OwnershipMatchSummary) -> float:
    if summary.files_with_owner <= 0:
        return 0.0
    counts: Counter[str] = Counter()
    for owners in summary.owner_by_file.values():
        for owner in owners:
            counts[owner] += 1
    if not counts:
        return 0.0
    return float(max(counts.values())) / float(summary.files_with_owner)


def zero_owner_found(summary: OwnershipMatchSummary) -> bool:
    return summary.files_with_owner == 0


def owner_overlap_with_active_candidates(
    *,
    owner_set: set[str],
    active_candidates: set[str],
) -> int:
    owners = {x.lower() for x in owner_set}
    candidates = {x.lower() for x in active_candidates}
    return len(owners & candidates)


def area_override_hit_rate(input: PRInputBundle, *, data_dir: str | Path) -> float:
    if not input.changed_files:
        return 0.0
    overrides = load_repo_area_overrides(repo_full_name=input.repo, data_dir=data_dir)
    if not overrides:
        return 0.0

    hits = 0
    for f in input.changed_files:
        default_area = default_area_for_path(f.path)
        resolved_area = input.file_areas.get(f.path, default_area)
        override_matched = any(fnmatch.fnmatchcase(f.path, rule.pattern) for rule in overrides)
        if override_matched and resolved_area != default_area:
            hits += 1
    return float(hits) / float(len(input.changed_files))


def conflicting_ownership_signals(
    *,
    input: PRInputBundle,
    summary: OwnershipMatchSummary,
) -> bool:
    if len(set(input.file_areas.values())) <= 1:
        return False
    broad_owner_set = owner_set_size(summary) >= 5
    low_coverage = owner_coverage_ratio(summary) < 0.5
    ambiguous_files = max_owners_on_any_file(summary) >= 3
    return (broad_owner_set and low_coverage) or ambiguous_files


def build_ownership_features(
    input: PRInputBundle,
    *,
    data_dir: str | Path,
    active_candidates: set[str] | None = None,
) -> dict[str, Any]:
    text = load_codeowners_text_for_pr(input=input, data_dir=data_dir)
    rules = parse_codeowners_rules(text or "")
    summary = match_codeowners_for_changed_files(input, rules=rules)

    owner_set_sorted = sorted(summary.owner_set, key=str.lower)

    out: dict[str, Any] = {
        "pr.ownership.owner_set": owner_set_sorted,
        "pr.ownership.owner_set_size": owner_set_size(summary),
        "pr.ownership.owner_coverage_ratio": owner_coverage_ratio(summary),
        "pr.ownership.zero_owner_found": zero_owner_found(summary),
        "pr.ownership.max_owners_on_any_file": max_owners_on_any_file(summary),
        "pr.ownership.top_owner_share": top_owner_share(summary),
        "pr.ownership.conflicting_ownership_signals": conflicting_ownership_signals(
            input=input,
            summary=summary,
        ),
        "pr.ownership.area_override_hit_rate": area_override_hit_rate(
            input,
            data_dir=data_dir,
        ),
        "pr.ownership.overlap_active_candidates_count": owner_overlap_with_active_candidates(
            owner_set=summary.owner_set,
            active_candidates=(active_candidates or set()),
        ),
    }

    # Compatibility aliases.
    out.update(
        {
            "pr.owners.owner_set_size": out["pr.ownership.owner_set_size"],
            "pr.owners.coverage_ratio": out["pr.ownership.owner_coverage_ratio"],
            "pr.owners.max_owners_any_file": out["pr.ownership.max_owners_on_any_file"],
            "pr.owners.top_owner_share": out["pr.ownership.top_owner_share"],
            "pr.owners.zero_owner_found": out["pr.ownership.zero_owner_found"],
            "pr.owners.overlap_active_candidates": out["pr.ownership.overlap_active_candidates_count"],
            "pr.owners.area_override_hit_rate": out["pr.ownership.area_override_hit_rate"],
            "pr.owners.conflicting_signals": out["pr.ownership.conflicting_ownership_signals"],
        }
    )

    return {k: out[k] for k in sorted(out)}
