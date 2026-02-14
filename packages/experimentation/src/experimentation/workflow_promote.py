from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from evaluation_harness.api import write_run_summary
from evaluation_harness.paths import repo_eval_run_dir
from repo_routing.runtime_defaults import DEFAULT_DATA_DIR

import json

from .workflow_helpers import _write_json


def experiment_promote(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    run_id: str = typer.Option(..., "--run-id", help="Evaluation run id"),
    data_dir: str = typer.Option(DEFAULT_DATA_DIR, help="Base directory for repo data"),
    output: str | None = typer.Option(
        None,
        help="Optional output JSON path (default: <run_dir>/promotion_summary.json)",
    ),
):
    run_dir = repo_eval_run_dir(repo_full_name=repo, data_dir=data_dir, run_id=run_id)
    if not run_dir.exists():
        raise typer.BadParameter(f"missing run dir: {run_dir}")

    summary_path = run_dir / "run_summary.json"
    summary: dict[str, Any] | None = None
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            summary = None
    if not isinstance(summary, dict):
        # Best-effort regeneration (offline, derived from existing artifacts).
        try:
            write_run_summary(repo=repo, run_id=run_id, run_dir=run_dir)
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise typer.BadParameter(
                f"unable to read or regenerate run_summary.json: {exc}"
            ) from exc

    gates = summary.get("gates") if isinstance(summary.get("gates"), dict) else {}
    promotion = (
        gates.get("promotion_evaluation")
        if isinstance(gates.get("promotion_evaluation"), dict)
        else None
    )
    quality = (
        gates.get("quality_gates")
        if isinstance(gates.get("quality_gates"), dict)
        else None
    )

    decision = "unknown"
    reasons: list[str] = []
    exit_code = 2

    if (
        quality is not None
        and isinstance(quality.get("all_pass"), bool)
        and not bool(quality.get("all_pass"))
    ):
        reasons.append("quality_gates_all_pass is false")

    if promotion is None:
        reasons.append("promotion_evaluation missing")
    else:
        eligible = promotion.get("eligible")
        if eligible is False:
            decision = "ineligible"
            reason = promotion.get("reason")
            if isinstance(reason, str) and reason.strip():
                reasons.append(reason.strip())
        elif eligible is True:
            promote = promotion.get("promote")
            if promote is True:
                if reasons:
                    decision = "do_not_promote"
                else:
                    decision = "promote"
                    exit_code = 0
            elif promote is False:
                decision = "do_not_promote"
            else:
                decision = "unknown"
        else:
            decision = "unknown"

    out_path = (
        Path(output) if output is not None else (run_dir / "promotion_summary.json")
    )
    payload: dict[str, Any] = {
        "schema_version": 1,
        "kind": "promotion_summary",
        "repo": repo,
        "run_id": run_id,
        "decision": decision,
        "reasons": sorted(
            set(str(r) for r in reasons if str(r).strip()), key=lambda s: s.lower()
        ),
        "promotion_evaluation": promotion,
        "quality_gates": quality,
        "artifacts": {
            "run_summary_json": str(summary_path),
            "report_json": str(run_dir / "report.json"),
            "per_pr_jsonl": str(run_dir / "per_pr.jsonl"),
        },
    }
    _write_json(out_path, payload)
    typer.echo(f"promotion_summary {out_path}")
    typer.echo(f"decision {decision}")

    if exit_code != 0:
        raise typer.Exit(code=exit_code)
