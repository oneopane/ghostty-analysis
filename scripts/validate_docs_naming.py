#!/usr/bin/env python3
"""Validate user-facing docs for deprecated terminology.

This check intentionally focuses on top-level onboarding docs/readmes where command
and package naming drift is most harmful.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]

CANDIDATE_PATHS = [
    "README.md",
    "docs/README.md",
    "docs/codebase-experimentation-guide.md",
    "docs/architecture-brief.md",
    "docs/examples/README.md",
    "docs/examples/e2e-unified-cli.md",
    "docs/examples/artifacts/*.md",
    "packages/cli/README.md",
    "packages/ingestion/README.md",
    "packages/inference/README.md",
    "packages/experimentation/README.md",
    "packages/evaluation/README.md",
]


@dataclass(frozen=True)
class Check:
    pattern: str
    message: str


CHECKS = [
    Check(r"\brepo routing\b", "deprecated CLI command 'repo routing'"),
    Check(r"\brepo eval\b", "deprecated CLI command 'repo eval'"),
    Check(r"\brepo-(ingestion|routing|cli)\b", "deprecated package/entrypoint names"),
    Check(
        r"\bevaluation-harness (run|show|list|sample|cutoff|explain)\b",
        "deprecated evaluation command prefix",
    ),
    Check(r"packages/repo-(ingestion|routing|cli)", "deprecated package paths"),
    Check(r"packages/evaluation-harness", "deprecated package path"),
    Check(
        r"packages/cli/src/repo_cli/unified_experiment\.py",
        "stale unified_experiment module path",
    ),
    Check(
        r"packages/cli/src/repo_cli/marimo_components\.py",
        "stale marimo_components module path",
    ),
]


def resolve_candidate_files() -> list[Path]:
    files: list[Path] = []
    for pattern in CANDIDATE_PATHS:
        if "*" in pattern or "?" in pattern or "[" in pattern:
            files.extend(path for path in ROOT_DIR.glob(pattern) if path.is_file())
        else:
            path = ROOT_DIR / pattern
            if path.is_file():
                files.append(path)
    unique = sorted({path.resolve() for path in files})
    return unique


def iter_hits(path: Path, regex: re.Pattern[str]) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if regex.search(line):
            hits.append((idx, line.strip()))
    return hits


def main() -> int:
    files = resolve_candidate_files()
    if not files:
        print("error: no docs files found for validation", file=sys.stderr)
        return 1

    failed = False
    for check in CHECKS:
        regex = re.compile(check.pattern)
        all_hits: list[tuple[Path, int, str]] = []
        for path in files:
            for line_no, snippet in iter_hits(path, regex):
                all_hits.append((path, line_no, snippet))

        if all_hits:
            failed = True
            print(f"[docs-check] FAIL: {check.message}")
            for path, line_no, snippet in all_hits:
                rel = path.relative_to(ROOT_DIR)
                print(f"{rel}:{line_no}: {snippet}")
            print()

    if failed:
        print("[docs-check] Deprecated naming detected.", file=sys.stderr)
        return 1

    print("[docs-check] Naming checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
