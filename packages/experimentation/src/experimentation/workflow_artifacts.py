from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from evaluation_harness.runner import RepoProfileRunSettings
from gh_history_ingestion.repo_artifacts.fetcher import fetch_pinned_repo_artifacts_sync
from repo_routing.history.reader import HistoryReader
from repo_routing.repo_profile.storage import (
    DEFAULT_PINNED_ARTIFACT_PATHS,
    pinned_artifact_path,
)


def _missing_artifact_paths(
    *,
    repo: str,
    data_dir: str,
    base_sha: str,
    artifact_paths: list[str],
) -> list[str]:
    missing: list[str] = []
    for rel in artifact_paths:
        p = pinned_artifact_path(
            repo_full_name=repo,
            base_sha=base_sha,
            relative_path=rel,
            data_dir=data_dir,
        )
        if not p.exists():
            missing.append(rel)
    return sorted(set(missing), key=str.lower)


def _prefetch_missing_artifacts(
    *,
    repo: str,
    data_dir: str,
    pr_numbers: list[int],
    cutoffs: dict[int, datetime],
    artifact_paths: list[str],
) -> dict[str, Any]:
    owner, name = repo.split("/", 1)
    seen_base_shas: set[str] = set()
    events: list[dict[str, Any]] = []

    with HistoryReader(repo_full_name=repo, data_dir=data_dir) as reader:
        for pr_number in pr_numbers:
            snapshot = reader.pull_request_snapshot(number=pr_number, as_of=cutoffs[pr_number])
            base_sha = snapshot.base_sha
            if not base_sha or base_sha in seen_base_shas:
                continue
            seen_base_shas.add(base_sha)

            missing = _missing_artifact_paths(
                repo=repo,
                data_dir=data_dir,
                base_sha=base_sha,
                artifact_paths=artifact_paths,
            )
            if not missing:
                continue

            manifest = fetch_pinned_repo_artifacts_sync(
                repo_full_name=repo,
                base_sha=base_sha,
                data_dir=data_dir,
                paths=missing,
            )
            manifest_path = (
                Path(data_dir)
                / "github"
                / owner
                / name
                / "repo_artifacts"
                / base_sha
                / "manifest.json"
            )

            events.append(
                {
                    "repo": repo,
                    "trigger_pr_number": pr_number,
                    "base_sha": base_sha,
                    "requested_paths": sorted(set(missing), key=str.lower),
                    "source": {
                        "provider": "github_contents_api",
                        "repo": repo,
                        "ref": base_sha,
                        "endpoint_template": "/repos/{owner}/{repo}/contents/{path}?ref={ref}",
                    },
                    "manifest_path": str(manifest_path),
                    "fetched_at": manifest.fetched_at,
                    "fetched_files": [
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
                        for f in sorted(manifest.files, key=lambda x: x.path.lower())
                    ],
                    "missing_after_fetch": sorted(
                        set(manifest.missing),
                        key=str.lower,
                    ),
                }
            )

    events.sort(key=lambda e: str(e.get("base_sha") or "").lower())
    return {
        "enabled": True,
        "network_used": bool(events),
        "requested_artifact_paths": sorted(set(artifact_paths), key=str.lower),
        "events": events,
    }


def _default_prefetch_summary(*, artifact_paths: list[str]) -> dict[str, Any]:
    return {
        "enabled": False,
        "network_used": False,
        "requested_artifact_paths": sorted(set(artifact_paths), key=str.lower),
        "events": [],
    }


def _build_repo_profile_settings(spec_payload: dict[str, Any]) -> RepoProfileRunSettings | None:
    raw = spec_payload.get("repo_profile")
    if not isinstance(raw, dict):
        raw = {}
    enabled = bool(raw.get("enabled", True))
    if not enabled:
        return None
    artifact_paths = raw.get("artifact_paths")
    if not isinstance(artifact_paths, list) or not artifact_paths:
        artifact_paths = list(DEFAULT_PINNED_ARTIFACT_PATHS)
    critical = raw.get("critical_artifact_paths")
    if not isinstance(critical, list):
        critical = []
    return RepoProfileRunSettings(
        strict=bool(raw.get("strict", True)),
        artifact_paths=tuple(str(p) for p in artifact_paths),
        critical_artifact_paths=tuple(str(p) for p in critical),
    )
