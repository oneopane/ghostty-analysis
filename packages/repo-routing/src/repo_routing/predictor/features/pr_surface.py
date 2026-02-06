from __future__ import annotations

import re
from collections import Counter

from ...inputs.models import PRInputBundle
from .patterns import (
    CI_BUILD_PATH_HINTS,
    DOC_PATH_HINTS,
    LOCK_VENDOR_GENERATED_HINTS,
    TEST_PATH_HINTS,
    parent_directory,
    path_extension,
)
from .stats import median_int, normalized_entropy, safe_ratio


def _file_changes(input: PRInputBundle) -> list[int]:
    return [int(f.changes or 0) for f in input.changed_files]


def _file_additions(input: PRInputBundle) -> list[int]:
    return [int(f.additions or 0) for f in input.changed_files]


def _file_deletions(input: PRInputBundle) -> list[int]:
    return [int(f.deletions or 0) for f in input.changed_files]


def changed_file_count(input: PRInputBundle) -> int:
    return len(input.changed_files)


def total_additions(input: PRInputBundle) -> int:
    return sum(_file_additions(input))


def total_deletions(input: PRInputBundle) -> int:
    return sum(_file_deletions(input))


def total_churn(input: PRInputBundle) -> int:
    return sum(_file_changes(input))


def max_file_churn(input: PRInputBundle) -> int:
    changes = _file_changes(input)
    return max(changes) if changes else 0


def median_file_churn(input: PRInputBundle) -> float:
    return median_int(_file_changes(input))


def status_ratios(input: PRInputBundle) -> dict[str, float]:
    total = float(len(input.changed_files))
    status_counts = Counter((f.status or "unknown").lower() for f in input.changed_files)
    return {
        "added": safe_ratio(float(status_counts.get("added", 0)), total),
        "modified": safe_ratio(float(status_counts.get("modified", 0)), total),
        "removed": safe_ratio(float(status_counts.get("removed", 0)), total),
    }


def _contains_any(path: str, hints: tuple[str, ...]) -> bool:
    p = path.lower()
    return any(h in p for h in hints)


def touches_tests(input: PRInputBundle) -> bool:
    return any(_contains_any(f.path, TEST_PATH_HINTS) for f in input.changed_files)


def touches_docs(input: PRInputBundle) -> bool:
    for f in input.changed_files:
        p = f.path.lower()
        if _contains_any(p, DOC_PATH_HINTS) or p.endswith(".md") or p.endswith(".rst"):
            return True
    return False


def touches_ci_build(input: PRInputBundle) -> bool:
    for f in input.changed_files:
        p = f.path.lower()
        if _contains_any(p, CI_BUILD_PATH_HINTS):
            return True
        if p.endswith("makefile") or p.endswith(".github/workflows"):
            return True
    return False


def distinct_directories_count(input: PRInputBundle) -> int:
    return len({parent_directory(f.path) for f in input.changed_files})


def directory_entropy(input: PRInputBundle) -> float:
    dirs = Counter(parent_directory(f.path) for f in input.changed_files)
    return normalized_entropy(dirs.values())


def distinct_extensions_count(input: PRInputBundle) -> int:
    return len({path_extension(f.path) for f in input.changed_files})


def top_extension_share(input: PRInputBundle) -> float:
    n = len(input.changed_files)
    if n == 0:
        return 0.0
    ext_counts = Counter(path_extension(f.path) for f in input.changed_files)
    return safe_ratio(float(max(ext_counts.values())), float(n))


def includes_lock_vendor_generated(input: PRInputBundle) -> bool:
    return any(_contains_any(f.path, LOCK_VENDOR_GENERATED_HINTS) for f in input.changed_files)


def areas_count(input: PRInputBundle) -> int:
    return len({a for a in input.file_areas.values() if a})


def max_files_in_one_area(input: PRInputBundle) -> int:
    counts = Counter(a for a in input.file_areas.values() if a)
    return max(counts.values()) if counts else 0


def area_entropy(input: PRInputBundle) -> float:
    counts = Counter(a for a in input.file_areas.values() if a)
    return normalized_entropy(counts.values())


def is_multi_area(input: PRInputBundle) -> bool:
    return areas_count(input) > 1


def title_length_chars(input: PRInputBundle) -> int:
    return len((input.title or "").strip())


def body_length_chars(input: PRInputBundle) -> int:
    return len((input.body or "").strip())


def is_body_empty_or_near_empty(input: PRInputBundle) -> bool:
    return body_length_chars(input) <= 20


def mention_count(input: PRInputBundle) -> int:
    text = "\n".join([input.title or "", input.body or ""])
    return len(MENTION_RE.findall(text))


def url_count(input: PRInputBundle) -> int:
    return len(URL_RE.findall(input.body or ""))


def gate_completeness_score(input: PRInputBundle) -> float:
    missing = [
        input.gate_fields.missing_issue,
        input.gate_fields.missing_ai_disclosure,
        input.gate_fields.missing_provenance,
    ]
    present_count = sum(0 if m else 1 for m in missing)
    return safe_ratio(float(present_count), 3.0)


def build_pr_surface_features(input: PRInputBundle) -> dict[str, int | float | bool]:
    ratios = status_ratios(input)
    return {
        "pr.files.count": changed_file_count(input),
        "pr.churn.additions_total": total_additions(input),
        "pr.churn.deletions_total": total_deletions(input),
        "pr.churn.total": total_churn(input),
        "pr.churn.file_max": max_file_churn(input),
        "pr.churn.file_median": median_file_churn(input),
        "pr.files.status_added_ratio": ratios["added"],
        "pr.files.status_modified_ratio": ratios["modified"],
        "pr.files.status_removed_ratio": ratios["removed"],
        "pr.paths.touches_tests": touches_tests(input),
        "pr.paths.touches_docs": touches_docs(input),
        "pr.paths.touches_ci_build": touches_ci_build(input),
        "pr.paths.distinct_directories": distinct_directories_count(input),
        "pr.paths.directory_entropy": directory_entropy(input),
        "pr.paths.distinct_extensions": distinct_extensions_count(input),
        "pr.paths.top_extension_share": top_extension_share(input),
        "pr.paths.includes_lock_vendor_generated": includes_lock_vendor_generated(input),
        "pr.areas.count": areas_count(input),
        "pr.areas.max_files_one_area": max_files_in_one_area(input),
        "pr.areas.entropy": area_entropy(input),
        "pr.areas.is_multi": is_multi_area(input),
        "pr.text.title_length_chars": title_length_chars(input),
        "pr.text.body_length_chars": body_length_chars(input),
        "pr.text.body_empty_or_near_empty": is_body_empty_or_near_empty(input),
        "pr.text.mention_count": mention_count(input),
        "pr.text.url_count": url_count(input),
        "pr.gates.completeness_score": gate_completeness_score(input),
    }


MENTION_RE = re.compile(
    r"(?<![A-Za-z0-9_])@[A-Za-z0-9][A-Za-z0-9-]*(?:/[A-Za-z0-9][A-Za-z0-9-]*)?"
)
URL_RE = re.compile(r"https?://[^\s)\]]+")
STATUS_COUNTER_TYPE = Counter[str]
