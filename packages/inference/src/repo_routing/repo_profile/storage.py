from __future__ import annotations

import hashlib
from pathlib import Path

from ..paths import repo_artifact_path

CODEOWNERS_PATH_CANDIDATES: tuple[str, ...] = (
    ".github/CODEOWNERS",
    "CODEOWNERS",
    "docs/CODEOWNERS",
)

DEFAULT_PINNED_ARTIFACT_PATHS: tuple[str, ...] = (
    ".github/CODEOWNERS",
    "CODEOWNERS",
    "docs/CODEOWNERS",
    ".github/OWNERS",
    "OWNERS",
    ".github/teams.yml",
    "teams.yml",
    "CONTRIBUTING.md",
    ".github/CONTRIBUTING.md",
)


def normalize_relpath(path: str) -> str:
    raw = path.replace("\\", "/").strip()
    while raw.startswith("/"):
        raw = raw[1:]
    pieces = [p for p in raw.split("/") if p not in {"", "."}]
    if not pieces:
        raise ValueError(f"invalid pinned artifact path: {path!r}")
    if any(p == ".." for p in pieces):
        raise ValueError(f"path traversal is not allowed: {path!r}")
    return "/".join(pieces)


def pinned_artifact_path(
    *,
    repo_full_name: str,
    base_sha: str,
    relative_path: str,
    data_dir: str | Path,
) -> Path:
    rel = normalize_relpath(relative_path)
    return repo_artifact_path(
        repo_full_name=repo_full_name,
        base_sha=base_sha,
        relative_path=rel,
        data_dir=data_dir,
    )


def normalize_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def stable_sha256_text(value: str) -> str:
    payload = normalize_text(value).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def detect_type(path: str) -> str:
    p = path.lower()
    if p.endswith("codeowners"):
        return "codeowners"
    if p.endswith(".yml") or p.endswith(".yaml"):
        return "yaml"
    if p.endswith(".md"):
        return "markdown"
    if p.endswith(".json"):
        return "json"
    return "text"
