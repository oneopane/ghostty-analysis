from __future__ import annotations

from pathlib import Path


def repo_db_path(*, repo_full_name: str, data_dir: str | Path) -> Path:
    owner, repo = repo_full_name.split("/", 1)
    base = Path(data_dir)
    return base / "github" / owner / repo / "history.sqlite"


def repo_codeowners_dir(*, repo_full_name: str, data_dir: str | Path) -> Path:
    owner, repo = repo_full_name.split("/", 1)
    base = Path(data_dir)
    return base / "github" / owner / repo / "codeowners"


def repo_codeowners_path(
    *, repo_full_name: str, base_sha: str, data_dir: str | Path
) -> Path:
    return (
        repo_codeowners_dir(repo_full_name=repo_full_name, data_dir=data_dir)
        / base_sha
        / "CODEOWNERS"
    )


def repo_artifacts_dir(*, repo_full_name: str, data_dir: str | Path) -> Path:
    owner, repo = repo_full_name.split("/", 1)
    base = Path(data_dir)
    return base / "github" / owner / repo / "repo_artifacts"


def repo_artifact_base_dir(
    *, repo_full_name: str, base_sha: str, data_dir: str | Path
) -> Path:
    return (
        repo_artifacts_dir(repo_full_name=repo_full_name, data_dir=data_dir) / base_sha
    )


def repo_artifact_path(
    *,
    repo_full_name: str,
    base_sha: str,
    relative_path: str,
    data_dir: str | Path,
) -> Path:
    return (
        repo_artifact_base_dir(
            repo_full_name=repo_full_name, base_sha=base_sha, data_dir=data_dir
        )
        / relative_path
    )


def repo_boundary_artifacts_dir(*, repo_full_name: str, data_dir: str | Path) -> Path:
    owner, repo = repo_full_name.split("/", 1)
    base = Path(data_dir)
    return base / "github" / owner / repo / "artifacts" / "routing" / "boundary_model"
