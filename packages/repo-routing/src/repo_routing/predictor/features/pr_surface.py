from __future__ import annotations

import re
from collections import Counter

from ...inputs.models import PRInputBundle


def changed_file_count(input: PRInputBundle) -> int:
    """Feature #1: number of changed files.

    Derivation: `len(input.changed_files)` from as-of snapshot.
    """
    raise NotImplementedError


def total_additions(input: PRInputBundle) -> int:
    """Feature #2: total additions.

    Derivation: sum `additions` across `input.changed_files` (from pull_request_files@head_sha).
    """
    raise NotImplementedError


def total_deletions(input: PRInputBundle) -> int:
    """Feature #3: total deletions.

    Derivation: sum `deletions` across `input.changed_files`.
    """
    raise NotImplementedError


def total_churn(input: PRInputBundle) -> int:
    """Feature #4: total changes/churn.

    Derivation: sum `changes` across `input.changed_files`.
    """
    raise NotImplementedError


def max_file_churn(input: PRInputBundle) -> int:
    """Feature #5: max file churn.

    Derivation: max `changes` across changed files.
    """
    raise NotImplementedError


def median_file_churn(input: PRInputBundle) -> float:
    """Feature #6: median file churn.

    Derivation: median of per-file `changes` values from changed files list.
    """
    raise NotImplementedError


def status_ratios(input: PRInputBundle) -> dict[str, float]:
    """Feature #7: ratios by file status (added/modified/removed).

    Derivation: count statuses from pull_request_files.status and normalize by file count.
    """
    raise NotImplementedError


def touches_tests(input: PRInputBundle) -> bool:
    """Feature #8: binary test-surface indicator.

    Derivation: any changed file path matches test-like patterns (tests/, __tests__, etc).
    """
    raise NotImplementedError


def touches_docs(input: PRInputBundle) -> bool:
    """Feature #9: binary docs-surface indicator.

    Derivation: path prefix checks (docs/) and extension checks (.md/.rst).
    """
    raise NotImplementedError


def touches_ci_build(input: PRInputBundle) -> bool:
    """Feature #10: binary build/CI indicator.

    Derivation: path matches .github/, ci/, build/, workflow-like files, Makefile.
    """
    raise NotImplementedError


def distinct_directories_count(input: PRInputBundle) -> int:
    """Feature #11: number of unique parent directories touched.

    Derivation: parent dir set over changed file paths.
    """
    raise NotImplementedError


def directory_entropy(input: PRInputBundle) -> float:
    """Feature #12: entropy over touched directories.

    Derivation: count files per parent directory, then compute Shannon entropy.
    """
    raise NotImplementedError


def distinct_extensions_count(input: PRInputBundle) -> int:
    """Feature #13: number of unique file extensions.

    Derivation: normalize extension per path, count unique values.
    """
    raise NotImplementedError


def top_extension_share(input: PRInputBundle) -> float:
    """Feature #14: dominant extension share.

    Derivation: max(files_in_extension / total_files).
    """
    raise NotImplementedError


def includes_lock_vendor_generated(input: PRInputBundle) -> bool:
    """Feature #15: lock/vendor/generated indicator.

    Derivation: path/filename pattern match for lockfiles, vendor/, dist/, generated/.
    """
    raise NotImplementedError


def areas_count(input: PRInputBundle) -> int:
    """Feature #16: number of unique areas touched.

    Derivation: `len(set(input.file_areas.values()))` (already as-of + deterministic mapping).
    """
    raise NotImplementedError


def max_files_in_one_area(input: PRInputBundle) -> int:
    """Feature #17: dominant area mass.

    Derivation: count files per area from `input.file_areas`, take max.
    """
    raise NotImplementedError


def area_entropy(input: PRInputBundle) -> float:
    """Feature #18: entropy over area distribution.

    Derivation: count files per area, compute Shannon entropy.
    """
    raise NotImplementedError


def is_multi_area(input: PRInputBundle) -> bool:
    """Feature #19: binary multi-area flag.

    Derivation: `areas_count > 1`.
    """
    raise NotImplementedError


def title_length_chars(input: PRInputBundle) -> int:
    """Feature #20: PR title length.

    Derivation: character length of as-of title.
    """
    raise NotImplementedError


def body_length_chars(input: PRInputBundle) -> int:
    """Feature #21: PR body length.

    Derivation: character length of as-of body.
    """
    raise NotImplementedError


def is_body_empty_or_near_empty(input: PRInputBundle) -> bool:
    """Feature #22: binary empty/near-empty body flag.

    Derivation: body stripped length threshold (e.g., 0..N chars).
    """
    raise NotImplementedError


def mention_count(input: PRInputBundle) -> int:
    """Feature #23: count of @mentions in title+body.

    Derivation: regex over `input.title` and `input.body` for @user / @org/team tokens.
    """
    raise NotImplementedError


def url_count(input: PRInputBundle) -> int:
    """Feature #24: count of URLs in PR body.

    Derivation: regex match for http(s) links in body.
    """
    raise NotImplementedError


def gate_completeness_score(input: PRInputBundle) -> float:
    """Feature #25: fraction of required gate fields present.

    Derivation: from `input.gate_fields` missing booleans; score in [0,1].
    """
    raise NotImplementedError


def build_pr_surface_features(input: PRInputBundle) -> dict[str, int | float | bool]:
    """Assemble PR surface family features (#1-#25).

    High-level implementation plan:
    - Compute each feature above from PRInputBundle only (no extra SQL required).
    - Return flat deterministic dict with stable key naming (`pr.*`).
    """
    raise NotImplementedError


MENTION_RE = re.compile(r"(?<![A-Za-z0-9_])@[A-Za-z0-9][A-Za-z0-9-]*(?:/[A-Za-z0-9][A-Za-z0-9-]*)?")
URL_RE = re.compile(r"https?://[^\s)\]]+")
STATUS_COUNTER_TYPE = Counter[str]
