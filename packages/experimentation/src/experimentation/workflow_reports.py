from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import typer
from evaluation_harness.paths import (
    eval_per_pr_jsonl_path,
    eval_report_json_path,
)
from repo_routing.registry import RouterSpec, router_id_for_spec
from repo_routing.time import require_dt_utc


EXPERIMENT_MANIFEST_FILENAME = "experiment_manifest.json"


def _iso_utc(dt: datetime) -> str:
    normalized = require_dt_utc(dt)
    return normalized.isoformat().replace("+00:00", "Z")


def _run_context_payload(
    *,
    repo: str,
    run_id: str,
    cohort_path: Path | None,
    spec_path: Path | None,
    cohort_payload: dict[str, Any],
    spec_payload: dict[str, Any],
    router_specs: list[RouterSpec],
    cutoff_source: str,
    pr_cutoffs: dict[int, datetime],
    artifact_prefetch: dict[str, Any],
) -> dict[str, Any]:
    return {
        "kind": "experiment_manifest",
        "version": "v1",
        "repo": repo,
        "run_id": run_id,
        "cohort_hash": cohort_payload["hash"],
        "experiment_spec_hash": spec_payload["hash"],
        "cohort_source_path": None if cohort_path is None else str(cohort_path),
        "spec_source_path": None if spec_path is None else str(spec_path),
        "cutoff_source": cutoff_source,
        "pr_cutoffs": {str(n): _iso_utc(pr_cutoffs[n]) for n in sorted(pr_cutoffs)},
        "artifact_prefetch": artifact_prefetch,
        "routers": [router_id_for_spec(s) for s in router_specs],
    }


def _load_run_context(run_dir: Path) -> dict[str, Any]:
    p = run_dir / EXPERIMENT_MANIFEST_FILENAME
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _load_per_pr_rows(*, repo: str, run_id: str, data_dir: str) -> list[dict[str, Any]]:
    p = eval_per_pr_jsonl_path(repo_full_name=repo, data_dir=data_dir, run_id=run_id)
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _load_report(*, repo: str, run_id: str, data_dir: str) -> dict[str, Any]:
    p = eval_report_json_path(repo_full_name=repo, data_dir=data_dir, run_id=run_id)
    if not p.exists():
        raise typer.BadParameter(f"missing report.json for run {run_id}: {p}")
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise typer.BadParameter(f"invalid report.json for run {run_id}: {p}")
    return raw


def _delta(a: object, b: object) -> str:
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return "n/a"
    return f"{float(b) - float(a):+.4f}"
