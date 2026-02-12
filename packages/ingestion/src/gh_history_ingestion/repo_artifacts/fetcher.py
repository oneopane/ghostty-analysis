from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from ..providers.github.auth import select_auth_token
from ..providers.github.client import GitHubRestClient

DEFAULT_PINNED_FILE_ALLOWLIST: tuple[str, ...] = (
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


@dataclass(frozen=True)
class PinnedArtifactFile:
    path: str
    content_sha256: str
    size_bytes: int
    detected_type: str
    blob_sha: str | None = None
    source_url: str | None = None
    git_url: str | None = None
    download_url: str | None = None


@dataclass(frozen=True)
class PinnedArtifactManifest:
    repo: str
    base_sha: str
    fetched_at: str
    files: list[PinnedArtifactFile]
    missing: list[str]

    def to_json_dict(self) -> dict[str, object]:
        files = [
            {
                "path": f.path,
                "content_sha256": f.content_sha256,
                "size_bytes": f.size_bytes,
                "detected_type": f.detected_type,
                "blob_sha": f.blob_sha,
                "source_url": f.source_url,
                "git_url": f.git_url,
                "download_url": f.download_url,
            }
            for f in sorted(self.files, key=lambda x: x.path.lower())
        ]
        return {
            "kind": "pinned_repo_artifact_manifest",
            "version": "v1",
            "repo": self.repo,
            "base_sha": self.base_sha,
            "fetched_at": self.fetched_at,
            "files": files,
            "missing": sorted(self.missing, key=str.lower),
        }


def _normalize_relpath(path: str) -> str:
    raw = path.replace("\\", "/").strip()
    while raw.startswith("/"):
        raw = raw[1:]
    parts = [p for p in raw.split("/") if p not in {"", "."}]
    if not parts:
        raise ValueError(f"invalid pinned artifact path: {path!r}")
    if any(p == ".." for p in parts):
        raise ValueError(f"path traversal is not allowed: {path!r}")
    return "/".join(parts)


def _normalize_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _detect_type(path: str) -> str:
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


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _repo_artifact_base_dir(
    *, repo_full_name: str, data_dir: str | Path, base_sha: str
) -> Path:
    owner, repo = repo_full_name.split("/", 1)
    return Path(data_dir) / "github" / owner / repo / "repo_artifacts" / base_sha


def _repo_artifact_manifest_path(
    *, repo_full_name: str, data_dir: str | Path, base_sha: str
) -> Path:
    return (
        _repo_artifact_base_dir(
            repo_full_name=repo_full_name, data_dir=data_dir, base_sha=base_sha
        )
        / "manifest.json"
    )


def _decode_content(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    content = payload.get("content")
    if not isinstance(content, str):
        return None
    encoding = str(payload.get("encoding") or "").lower()
    if encoding == "base64":
        raw = base64.b64decode(content)
        return raw.decode("utf-8", errors="replace")
    return str(content)


def _is_not_found(exc: Exception) -> bool:
    return "404" in str(exc)


async def fetch_pinned_repo_artifacts(
    *,
    repo_full_name: str,
    base_sha: str,
    data_dir: str | Path = "data",
    paths: Sequence[str] | None = None,
    client: GitHubRestClient | None = None,
) -> PinnedArtifactManifest:
    owner, repo = repo_full_name.split("/", 1)
    requested = sorted(
        {_normalize_relpath(p) for p in (paths or DEFAULT_PINNED_FILE_ALLOWLIST)},
        key=str.lower,
    )

    created_client = False
    gh = client
    if gh is None:
        gh = GitHubRestClient(token=select_auth_token())
        created_client = True

    files: list[PinnedArtifactFile] = []
    missing: list[str] = []
    base_dir = _repo_artifact_base_dir(
        repo_full_name=repo_full_name, data_dir=data_dir, base_sha=base_sha
    )
    base_dir.mkdir(parents=True, exist_ok=True)

    try:
        if created_client:
            await gh.__aenter__()
        for rel in requested:
            endpoint = f"/repos/{owner}/{repo}/contents/{rel}"
            try:
                payload = await gh.get_json(endpoint, params={"ref": base_sha})
            except Exception as exc:
                if _is_not_found(exc):
                    missing.append(rel)
                    continue
                raise

            text = _decode_content(payload)
            if text is None:
                missing.append(rel)
                continue

            normalized = _normalize_text(text)
            out = base_dir / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(normalized, encoding="utf-8")

            blob_sha = None
            source_url = None
            git_url = None
            download_url = None
            if isinstance(payload, dict):
                if payload.get("sha") is not None:
                    blob_sha = str(payload.get("sha"))
                if payload.get("url") is not None:
                    source_url = str(payload.get("url"))
                if payload.get("git_url") is not None:
                    git_url = str(payload.get("git_url"))
                if payload.get("download_url") is not None:
                    download_url = str(payload.get("download_url"))

            files.append(
                PinnedArtifactFile(
                    path=rel,
                    content_sha256=_sha256_text(normalized),
                    size_bytes=len(normalized.encode("utf-8")),
                    detected_type=_detect_type(rel),
                    blob_sha=blob_sha,
                    source_url=source_url,
                    git_url=git_url,
                    download_url=download_url,
                )
            )
    finally:
        if created_client:
            await gh.__aexit__(None, None, None)

    manifest = PinnedArtifactManifest(
        repo=repo_full_name,
        base_sha=base_sha,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        files=files,
        missing=missing,
    )
    mp = _repo_artifact_manifest_path(
        repo_full_name=repo_full_name, data_dir=data_dir, base_sha=base_sha
    )
    mp.write_text(
        json.dumps(
            manifest.to_json_dict(),
            sort_keys=True,
            indent=2,
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def fetch_pinned_repo_artifacts_sync(
    *,
    repo_full_name: str,
    base_sha: str,
    data_dir: str | Path = "data",
    paths: Iterable[str] | None = None,
) -> PinnedArtifactManifest:
    return asyncio.run(
        fetch_pinned_repo_artifacts(
            repo_full_name=repo_full_name,
            base_sha=base_sha,
            data_dir=data_dir,
            paths=tuple(paths) if paths is not None else None,
        )
    )
