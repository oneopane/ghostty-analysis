from __future__ import annotations

from pathlib import Path


def repo_eval_dir(*, repo_full_name: str, data_dir: str | Path) -> Path:
    owner, repo = repo_full_name.split("/", 1)
    base = Path(data_dir)
    return base / "github" / owner / repo / "eval"


def repo_eval_run_dir(
    *, repo_full_name: str, data_dir: str | Path, run_id: str
) -> Path:
    return repo_eval_dir(repo_full_name=repo_full_name, data_dir=data_dir) / run_id


def pr_dir(
    *, repo_full_name: str, data_dir: str | Path, run_id: str, pr_number: int
) -> Path:
    return (
        repo_eval_run_dir(
            repo_full_name=repo_full_name, data_dir=data_dir, run_id=run_id
        )
        / "prs"
        / str(pr_number)
    )


def pr_snapshot_path(
    *, repo_full_name: str, data_dir: str | Path, run_id: str, pr_number: int
) -> Path:
    return (
        pr_dir(
            repo_full_name=repo_full_name,
            data_dir=data_dir,
            run_id=run_id,
            pr_number=pr_number,
        )
        / "snapshot.json"
    )


def pr_routes_dir(
    *, repo_full_name: str, data_dir: str | Path, run_id: str, pr_number: int
) -> Path:
    return (
        pr_dir(
            repo_full_name=repo_full_name,
            data_dir=data_dir,
            run_id=run_id,
            pr_number=pr_number,
        )
        / "routes"
    )


def pr_route_result_path(
    *,
    repo_full_name: str,
    data_dir: str | Path,
    run_id: str,
    pr_number: int,
    baseline: str,
) -> Path:
    return (
        pr_routes_dir(
            repo_full_name=repo_full_name,
            data_dir=data_dir,
            run_id=run_id,
            pr_number=pr_number,
        )
        / f"{baseline}.json"
    )
