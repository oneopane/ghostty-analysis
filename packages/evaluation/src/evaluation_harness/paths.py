from __future__ import annotations

from pathlib import Path


def repo_db_path(*, repo_full_name: str, data_dir: str | Path) -> Path:
    owner, repo = repo_full_name.split("/", 1)
    base = Path(data_dir)
    return base / "github" / owner / repo / "history.sqlite"


def repo_eval_run_dir(
    *, repo_full_name: str, data_dir: str | Path, run_id: str
) -> Path:
    owner, repo = repo_full_name.split("/", 1)
    base = Path(data_dir)
    return base / "github" / owner / repo / "eval" / run_id


def repo_eval_dir(*, repo_full_name: str, data_dir: str | Path) -> Path:
    owner, repo = repo_full_name.split("/", 1)
    base = Path(data_dir)
    return base / "github" / owner / repo / "eval"


def eval_run_dir(*, repo_full_name: str, data_dir: str | Path, run_id: str) -> Path:
    # Back-compat alias; prefer repo_eval_run_dir.
    return repo_eval_run_dir(
        repo_full_name=repo_full_name, data_dir=data_dir, run_id=run_id
    )


def eval_manifest_path(
    *, repo_full_name: str, data_dir: str | Path, run_id: str
) -> Path:
    return (
        repo_eval_run_dir(
            repo_full_name=repo_full_name, data_dir=data_dir, run_id=run_id
        )
        / "manifest.json"
    )


def eval_report_md_path(
    *, repo_full_name: str, data_dir: str | Path, run_id: str
) -> Path:
    return (
        repo_eval_run_dir(
            repo_full_name=repo_full_name, data_dir=data_dir, run_id=run_id
        )
        / "report.md"
    )


def eval_report_json_path(
    *, repo_full_name: str, data_dir: str | Path, run_id: str
) -> Path:
    return (
        repo_eval_run_dir(
            repo_full_name=repo_full_name, data_dir=data_dir, run_id=run_id
        )
        / "report.json"
    )


def eval_per_pr_jsonl_path(
    *, repo_full_name: str, data_dir: str | Path, run_id: str
) -> Path:
    return (
        repo_eval_run_dir(
            repo_full_name=repo_full_name, data_dir=data_dir, run_id=run_id
        )
        / "per_pr.jsonl"
    )
