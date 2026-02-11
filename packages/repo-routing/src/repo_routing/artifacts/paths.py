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


def pr_inputs_path(
    *, repo_full_name: str, data_dir: str | Path, run_id: str, pr_number: int
) -> Path:
    return (
        pr_dir(
            repo_full_name=repo_full_name,
            data_dir=data_dir,
            run_id=run_id,
            pr_number=pr_number,
        )
        / "inputs.json"
    )


def pr_features_path(
    *,
    repo_full_name: str,
    data_dir: str | Path,
    run_id: str,
    pr_number: int,
    router_id: str,
) -> Path:
    return (
        pr_dir(
            repo_full_name=repo_full_name,
            data_dir=data_dir,
            run_id=run_id,
            pr_number=pr_number,
        )
        / "features"
        / f"{router_id}.json"
    )


def pr_llm_step_path(
    *,
    repo_full_name: str,
    data_dir: str | Path,
    run_id: str,
    pr_number: int,
    router_id: str,
    step: str,
) -> Path:
    return (
        pr_dir(
            repo_full_name=repo_full_name,
            data_dir=data_dir,
            run_id=run_id,
            pr_number=pr_number,
        )
        / "llm"
        / router_id
        / f"{step}.json"
    )


def pr_route_result_path(
    *,
    repo_full_name: str,
    data_dir: str | Path,
    run_id: str,
    pr_number: int,
    baseline: str | None = None,
    router_id: str | None = None,
) -> Path:
    rid = (router_id or baseline or "router").strip()
    return (
        pr_routes_dir(
            repo_full_name=repo_full_name,
            data_dir=data_dir,
            run_id=run_id,
            pr_number=pr_number,
        )
        / f"{rid}.json"
    )


def pr_repo_profile_dir(
    *, repo_full_name: str, data_dir: str | Path, run_id: str, pr_number: int
) -> Path:
    return (
        pr_dir(
            repo_full_name=repo_full_name,
            data_dir=data_dir,
            run_id=run_id,
            pr_number=pr_number,
        )
        / "repo_profile"
    )


def pr_repo_profile_path(
    *, repo_full_name: str, data_dir: str | Path, run_id: str, pr_number: int
) -> Path:
    return (
        pr_repo_profile_dir(
            repo_full_name=repo_full_name,
            data_dir=data_dir,
            run_id=run_id,
            pr_number=pr_number,
        )
        / "profile.json"
    )


def pr_repo_profile_qa_path(
    *, repo_full_name: str, data_dir: str | Path, run_id: str, pr_number: int
) -> Path:
    return (
        pr_repo_profile_dir(
            repo_full_name=repo_full_name,
            data_dir=data_dir,
            run_id=run_id,
            pr_number=pr_number,
        )
        / "qa.json"
    )
