from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import PurePosixPath
from statistics import quantiles
from typing import Any

from ...inputs.models import PRInputBundle
from .patterns import (
    CI_BUILD_PATH_HINTS,
    DOC_PATH_HINTS,
    LOCK_VENDOR_GENERATED_HINTS,
    TEST_PATH_HINTS,
    WIP_TITLE_HINTS,
    path_extension,
)
from .boundary_utils import boundary_counts_from_file_boundaries
from .stats import median_int, normalized_entropy, safe_ratio

# Heuristic knobs (deterministic defaults; can be lifted into config later)
_LARGE_FILE_CHURN_THRESHOLD = 500
_BINARY_EXTS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "pdf",
    "zip",
    "gz",
    "jar",
    "mp4",
    "mov",
    "ico",
    "woff",
    "woff2",
    "ttf",
    "otf",
    "eot",
}
_HOTFIX_TITLE_HINTS = ("hotfix", "urgent", "sev", "security fix", "quick fix")

MENTION_RE = re.compile(
    r"(?<![A-Za-z0-9_])@(?P<id>[A-Za-z0-9][A-Za-z0-9-]*(?:/[A-Za-z0-9][A-Za-z0-9-]*)?)"
)
URL_RE = re.compile(r"https?://[^\s)\]]+")
ISSUE_REF_RE = re.compile(r"(?<!\w)#\d+\b|\b[A-Z][A-Z0-9]+-\d+\b")
CHECKLIST_RE = re.compile(r"(?im)^\s*[-*]\s*\[(?: |x|X)\]\s+.+$")
RISK_SECTION_RE = re.compile(r"(?i)\b(risk|blast\s*radius|rollback|mitigation)\b")


def _file_changes(input: PRInputBundle) -> list[int]:
    return [int(f.changes or (f.additions or 0) + (f.deletions or 0)) for f in input.changed_files]


def _contains_any(path: str, hints: tuple[str, ...]) -> bool:
    p = path.lower()
    return any(h in p for h in hints)


def _dirname_at_depth(path: str, depth: int) -> str:
    parts = [p for p in PurePosixPath(path).parts[:-1] if p not in {".", ""}]
    if not parts:
        return "__root__"
    return "/".join(parts[:depth])


def _directory_stats_by_depth(input: PRInputBundle, depth: int) -> tuple[int, float]:
    buckets = Counter(_dirname_at_depth(f.path, depth) for f in input.changed_files)
    return len(buckets), normalized_entropy(buckets.values())


def _status_bucket(status: str | None) -> str:
    s = (status or "unknown").lower()
    if s in {"removed", "deleted"}:
        return "deleted"
    if s == "renamed":
        return "renamed"
    if s == "added":
        return "added"
    if s == "modified":
        return "modified"
    return "modified"


def _as_epoch_seconds(ts: datetime | None) -> int | None:
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return int(ts.timestamp())


def _body_text(input: PRInputBundle) -> str:
    return (input.body or "").strip()


def build_pr_surface_features(input: PRInputBundle) -> dict[str, Any]:
    changes = _file_changes(input)
    files_n = len(input.changed_files)

    additions_total = sum(int(f.additions or 0) for f in input.changed_files)
    deletions_total = sum(int(f.deletions or 0) for f in input.changed_files)
    churn_total = sum(changes)

    status_counts = Counter(_status_bucket(f.status) for f in input.changed_files)
    ext_counts = Counter(path_extension(f.path) for f in input.changed_files)

    depth2_count, depth2_entropy = _directory_stats_by_depth(input, 2)
    depth3_count, depth3_entropy = _directory_stats_by_depth(input, 3)
    depth4_count, depth4_entropy = _directory_stats_by_depth(input, 4)

    mention_ids = [m.group("id") for m in MENTION_RE.finditer("\n".join([input.title or "", input.body or ""]))]
    mention_users = sorted({m for m in mention_ids if "/" not in m}, key=str.lower)
    mention_teams = sorted({m for m in mention_ids if "/" in m}, key=str.lower)

    boundaries_sorted = sorted({b for b in input.boundaries if b}, key=str.lower)
    boundary_counts = boundary_counts_from_file_boundaries(input.file_boundaries)

    missing_fields = [
        bool(input.gate_fields.missing_issue),
        bool(input.gate_fields.missing_ai_disclosure),
        bool(input.gate_fields.missing_provenance),
    ]
    present_count = sum(0 if m else 1 for m in missing_fields)

    body = _body_text(input)
    title_l = (input.title or "").lower()

    churn_p90 = 0.0
    if len(changes) >= 2:
        churn_p90 = float(quantiles(changes, n=10, method="inclusive")[8])
    elif len(changes) == 1:
        churn_p90 = float(changes[0])

    out: dict[str, Any] = {
        # A1: meta
        "pr.meta.author_login": input.author_login,
        "pr.meta.author_type": "bot" if (input.author_login or "").lower().endswith("[bot]") else "user",
        "pr.meta.created_at_ts": _as_epoch_seconds(input.snapshot.created_at),
        "pr.meta.is_draft": None,
        "pr.meta.base_ref": input.snapshot.base_ref,
        "pr.meta.base_sha": input.snapshot.base_sha,
        "pr.meta.head_sha": input.snapshot.head_sha,
        "pr.meta.title_len_chars": len((input.title or "").strip()),
        "pr.meta.body_len_chars": len(body),
        "pr.meta.body_is_emptyish": len(body) <= 20,
        "pr.meta.title_has_wip_signal": any(h in title_l for h in WIP_TITLE_HINTS),
        "pr.meta.title_has_hotfix_signal": any(h in title_l for h in _HOTFIX_TITLE_HINTS),
        "pr.meta.mentions.count": len(mention_ids),
        "pr.meta.mentions.users_count": len(mention_users),
        "pr.meta.mentions.teams_count": len(mention_teams),
        "pr.meta.urls.count": len(URL_RE.findall(body)),
        "pr.meta.issue_refs.count": len(ISSUE_REF_RE.findall("\n".join([input.title or "", input.body or ""]))),
        "pr.meta.labels.count": len(input.snapshot.labels),
        "pr.meta.assignees.count": len(input.snapshot.assignees),
        "pr.meta.milestone.present": bool(input.snapshot.milestone_present),
        # A2: surface counts/churn
        "pr.surface.changed_file_count": files_n,
        "pr.surface.total_additions": additions_total,
        "pr.surface.total_deletions": deletions_total,
        "pr.surface.total_churn": churn_total,
        "pr.surface.max_file_churn": max(changes) if changes else 0,
        "pr.surface.median_file_churn": median_int(changes),
        "pr.surface.churn_p90": churn_p90,
        "pr.surface.status_ratio.added": safe_ratio(float(status_counts.get("added", 0)), float(files_n)),
        "pr.surface.status_ratio.modified": safe_ratio(float(status_counts.get("modified", 0)), float(files_n)),
        "pr.surface.status_ratio.deleted": safe_ratio(float(status_counts.get("deleted", 0)), float(files_n)),
        "pr.surface.status_ratio.renamed": safe_ratio(float(status_counts.get("renamed", 0)), float(files_n)),
        # A2: structure/entropy
        "pr.surface.distinct_directories_count.depth2": depth2_count,
        "pr.surface.distinct_directories_count.depth3": depth3_count,
        "pr.surface.distinct_directories_count.depth4": depth4_count,
        "pr.surface.directory_entropy.depth2": depth2_entropy,
        "pr.surface.directory_entropy.depth3": depth3_entropy,
        "pr.surface.directory_entropy.depth4": depth4_entropy,
        "pr.surface.distinct_extensions_count": len(ext_counts),
        "pr.surface.top_extension_share": safe_ratio(float(max(ext_counts.values()) if ext_counts else 0), float(files_n)),
        "pr.surface.extension_entropy": normalized_entropy(ext_counts.values()),
        # A2: heuristics
        "pr.surface.touches_tests": any(_contains_any(f.path, TEST_PATH_HINTS) for f in input.changed_files),
        "pr.surface.touches_docs": any(
            _contains_any(f.path, DOC_PATH_HINTS) or f.path.lower().endswith((".md", ".rst", ".txt"))
            for f in input.changed_files
        ),
        "pr.surface.touches_ci_build": any(
            _contains_any(f.path, CI_BUILD_PATH_HINTS) or f.path.lower().endswith("makefile")
            for f in input.changed_files
        ),
        "pr.surface.includes_lock_vendor_generated": any(
            _contains_any(f.path, LOCK_VENDOR_GENERATED_HINTS) for f in input.changed_files
        ),
        "pr.surface.binary_file_count": sum(1 for f in input.changed_files if path_extension(f.path) in _BINARY_EXTS),
        "pr.surface.large_file_touch_count": sum(
            1 for c in changes if int(c) >= _LARGE_FILE_CHURN_THRESHOLD
        ),
        # C1: boundaries
        "pr.boundary.set": boundaries_sorted,
        "pr.boundary.count": len(boundaries_sorted),
        "pr.boundary.max_files_in_one_boundary": max(boundary_counts.values()) if boundary_counts else 0,
        "pr.boundary.boundary_entropy": normalized_entropy(boundary_counts.values()),
        "pr.boundary.is_multi_boundary": len(boundaries_sorted) > 1,
        # Geometry-lite (shape at cutoff)
        "pr.geometry.shape.boundary_entropy": normalized_entropy(boundary_counts.values()),
        "pr.geometry.shape.boundary_top_share": safe_ratio(
            float(max(boundary_counts.values()) if boundary_counts else 0),
            float(files_n),
        ),
        "pr.geometry.shape.directory_entropy.depth3": depth3_entropy,
        "pr.geometry.shape.extension_entropy": normalized_entropy(ext_counts.values()),
        # A3: gates
        "pr.gates.completeness_score": safe_ratio(float(present_count), 3.0),
        "pr.gates.missing_required_fields_count": sum(1 for m in missing_fields if m),
        "pr.gates.has_ai_disclosure": not bool(input.gate_fields.missing_ai_disclosure),
        "pr.gates.has_provenance": not bool(input.gate_fields.missing_provenance),
        "pr.gates.has_checklist_markers": bool(CHECKLIST_RE.search(body)),
        "pr.gates.has_risk_section": bool(RISK_SECTION_RE.search(body)),
    }

    # Compatibility aliases used by current tests/weights.
    out.update(
        {
            "pr.files.count": out["pr.surface.changed_file_count"],
            "pr.churn.additions_total": out["pr.surface.total_additions"],
            "pr.churn.deletions_total": out["pr.surface.total_deletions"],
            "pr.churn.total": out["pr.surface.total_churn"],
            "pr.churn.file_max": out["pr.surface.max_file_churn"],
            "pr.churn.file_median": out["pr.surface.median_file_churn"],
            "pr.files.status_added_ratio": out["pr.surface.status_ratio.added"],
            "pr.files.status_modified_ratio": out["pr.surface.status_ratio.modified"],
            "pr.files.status_removed_ratio": out["pr.surface.status_ratio.deleted"],
            "pr.paths.touches_tests": out["pr.surface.touches_tests"],
            "pr.paths.touches_docs": out["pr.surface.touches_docs"],
            "pr.paths.touches_ci_build": out["pr.surface.touches_ci_build"],
            "pr.paths.distinct_directories": out["pr.surface.distinct_directories_count.depth3"],
            "pr.paths.directory_entropy": out["pr.surface.directory_entropy.depth3"],
            "pr.paths.distinct_extensions": out["pr.surface.distinct_extensions_count"],
            "pr.paths.top_extension_share": out["pr.surface.top_extension_share"],
            "pr.paths.includes_lock_vendor_generated": out["pr.surface.includes_lock_vendor_generated"],
            "pr.boundary.max_files_one_boundary": out["pr.boundary.max_files_in_one_boundary"],
            "pr.boundary.entropy": out["pr.boundary.boundary_entropy"],
            "pr.boundary.is_multi": out["pr.boundary.is_multi_boundary"],
            "pr.text.title_length_chars": out["pr.meta.title_len_chars"],
            "pr.text.body_length_chars": out["pr.meta.body_len_chars"],
            "pr.text.body_empty_or_near_empty": out["pr.meta.body_is_emptyish"],
            "pr.text.mention_count": out["pr.meta.mentions.count"],
            "pr.text.url_count": out["pr.meta.urls.count"],
        }
    )

    return {k: out[k] for k in sorted(out)}
