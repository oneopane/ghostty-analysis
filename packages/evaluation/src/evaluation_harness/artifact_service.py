from __future__ import annotations

import json

from .paths import repo_eval_run_dir


def list_artifacts(*, repo: str, run_id: str, data_dir: str = "data") -> list[dict[str, object]]:
    idx = repo_eval_run_dir(repo_full_name=repo, data_dir=data_dir, run_id=run_id) / "artifact_index.jsonl"
    if not idx.exists():
        return []
    return [
        json.loads(line)
        for line in idx.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def show_artifact(
    *,
    repo: str,
    run_id: str,
    artifact_id: str,
    data_dir: str = "data",
) -> dict[str, object]:
    run_dir = repo_eval_run_dir(repo_full_name=repo, data_dir=data_dir, run_id=run_id)
    rows = list_artifacts(repo=repo, run_id=run_id, data_dir=data_dir)
    row = next((r for r in rows if r.get("artifact_id") == artifact_id), None)
    if row is None:
        raise FileNotFoundError(artifact_id)
    p = run_dir / str(row["relative_path"])
    return json.loads(p.read_text(encoding="utf-8"))
