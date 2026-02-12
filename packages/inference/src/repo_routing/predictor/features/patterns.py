from __future__ import annotations

from pathlib import PurePosixPath

# NOTE: These are starter heuristics only. Keep deterministic and repo-agnostic.
TEST_PATH_HINTS: tuple[str, ...] = (
    "test/",
    "tests/",
    "__tests__/",
    "spec/",
)

DOC_PATH_HINTS: tuple[str, ...] = (
    "docs/",
    "doc/",
)

CI_BUILD_PATH_HINTS: tuple[str, ...] = (
    ".github/",
    "ci/",
    "build/",
    ".circleci/",
)

LOCK_VENDOR_GENERATED_HINTS: tuple[str, ...] = (
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Cargo.lock",
    "Pipfile.lock",
    "vendor/",
    "dist/",
    "generated/",
)

WIP_TITLE_HINTS: tuple[str, ...] = (
    "wip",
    "do not review",
    "dnr",
)


def path_extension(path: str) -> str:
    """Return normalized extension (without dot), or '__none__'."""
    suffix = PurePosixPath(path).suffix.lower().lstrip(".")
    return suffix or "__none__"


def parent_directory(path: str) -> str:
    """Return normalized parent dir key, or '__root__' for root files."""
    parent = str(PurePosixPath(path).parent)
    return "__root__" if parent in {"", "."} else parent
