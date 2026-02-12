from __future__ import annotations

from datetime import datetime
from pathlib import Path

from repo_routing.registry import RouterSpec

from .config import EvalRunConfig
from .runner_aggregate import aggregate_eval_stage
from .runner_emit import emit_eval_stage
from .runner_models import RepoProfileRunSettings, RunResult
from .runner_per_pr import per_pr_evaluate_stage
from harness.runner.prepare import prepare_eval_stage


def run_streaming_eval(
    *,
    cfg: EvalRunConfig,
    pr_numbers: list[int],
    baselines: list[str] | None = None,
    router_specs: list[RouterSpec] | None = None,
    router_config_path: str | Path | None = None,
    repo_profile_settings: RepoProfileRunSettings | None = None,
    pr_cutoffs: dict[int | str, datetime] | None = None,
) -> RunResult:
    """Run a leakage-safe streaming evaluation."""

    prepared = prepare_eval_stage(
        cfg=cfg,
        pr_numbers=pr_numbers,
        baselines=baselines,
        router_specs=router_specs,
        router_config_path=router_config_path,
        pr_cutoffs=pr_cutoffs,
    )
    per_pr = per_pr_evaluate_stage(
        prepared=prepared,
        repo_profile_settings=repo_profile_settings,
    )
    aggregated = aggregate_eval_stage(prepared=prepared, per_pr=per_pr)
    return emit_eval_stage(prepared=prepared, per_pr=per_pr, aggregated=aggregated)


__all__ = [
    "RepoProfileRunSettings",
    "RunResult",
    "run_streaming_eval",
]
