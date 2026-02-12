from __future__ import annotations

from pathlib import Path


def repo_boundary_artifacts_dir(*, repo_full_name: str, data_dir: str | Path) -> Path:
    owner, repo = repo_full_name.split("/", 1)
    base = Path(data_dir)
    return base / "github" / owner / repo / "artifacts" / "routing" / "boundary_model"


def boundary_model_dir(
    *,
    repo_full_name: str,
    data_dir: str | Path,
    strategy_id: str,
    cutoff_key: str,
) -> Path:
    return (
        repo_boundary_artifacts_dir(repo_full_name=repo_full_name, data_dir=data_dir)
        / strategy_id
        / cutoff_key
    )


def boundary_model_path(
    *,
    repo_full_name: str,
    data_dir: str | Path,
    strategy_id: str,
    cutoff_key: str,
) -> Path:
    return (
        boundary_model_dir(
            repo_full_name=repo_full_name,
            data_dir=data_dir,
            strategy_id=strategy_id,
            cutoff_key=cutoff_key,
        )
        / "boundary_model.json"
    )


def boundary_memberships_path(
    *,
    repo_full_name: str,
    data_dir: str | Path,
    strategy_id: str,
    cutoff_key: str,
) -> Path:
    return (
        boundary_model_dir(
            repo_full_name=repo_full_name,
            data_dir=data_dir,
            strategy_id=strategy_id,
            cutoff_key=cutoff_key,
        )
        / "memberships.parquet"
    )


def boundary_signals_path(
    *,
    repo_full_name: str,
    data_dir: str | Path,
    strategy_id: str,
    cutoff_key: str,
) -> Path:
    return (
        boundary_model_dir(
            repo_full_name=repo_full_name,
            data_dir=data_dir,
            strategy_id=strategy_id,
            cutoff_key=cutoff_key,
        )
        / "signals.parquet"
    )


def boundary_manifest_path(
    *,
    repo_full_name: str,
    data_dir: str | Path,
    strategy_id: str,
    cutoff_key: str,
) -> Path:
    return (
        boundary_model_dir(
            repo_full_name=repo_full_name,
            data_dir=data_dir,
            strategy_id=strategy_id,
            cutoff_key=cutoff_key,
        )
        / "manifest.json"
    )
