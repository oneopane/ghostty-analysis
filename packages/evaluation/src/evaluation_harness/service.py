from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from repo_routing.registry import RouterSpec

from .config import EvalRunConfig
from .paths import (
    eval_per_pr_jsonl_path,
    eval_report_json_path,
    eval_report_md_path,
    repo_eval_dir,
)
from .runner import RepoProfileRunSettings, RunResult, run_streaming_eval


def run(
    *,
    cfg: EvalRunConfig,
    pr_numbers: list[int],
    baselines: list[str] | None = None,
    router_specs: list[RouterSpec] | None = None,
    router_config_path: str | Path | None = None,
    repo_profile_settings: RepoProfileRunSettings | None = None,
    pr_cutoffs: dict[int | str, datetime] | None = None,
) -> RunResult:
    return run_streaming_eval(
        cfg=cfg,
        pr_numbers=pr_numbers,
        baselines=baselines,
        router_specs=router_specs,
        router_config_path=router_config_path,
        repo_profile_settings=repo_profile_settings,
        pr_cutoffs=pr_cutoffs,
    )


def list_runs(
    *,
    repo: str,
    data_dir: str = "data",
) -> list[str]:
    base = repo_eval_dir(repo_full_name=repo, data_dir=data_dir)
    if not base.exists():
        raise FileNotFoundError(str(base))

    runs = [p.name for p in base.iterdir() if p.is_dir()]
    runs.sort(key=lambda s: s.lower())
    return runs


def show(
    *,
    repo: str,
    run_id: str,
    data_dir: str = "data",
) -> str:
    p = eval_report_md_path(repo_full_name=repo, data_dir=data_dir, run_id=run_id)
    if p.exists():
        return p.read_text(encoding="utf-8").rstrip("\n")

    pj = eval_report_json_path(repo_full_name=repo, data_dir=data_dir, run_id=run_id)
    if pj.exists():
        return pj.read_text(encoding="utf-8").rstrip("\n")

    raise FileNotFoundError(f"{p} / {pj}")


def explain(
    *,
    repo: str,
    run_id: str,
    pr_number: int,
    baseline: str | None = None,
    router: str | None = None,
    policy: str | None = None,
    data_dir: str = "data",
) -> str:
    p = eval_per_pr_jsonl_path(repo_full_name=repo, data_dir=data_dir, run_id=run_id)
    if not p.exists():
        raise FileNotFoundError(f"missing per_pr.jsonl: {p}")

    row: dict | None = None
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if int(obj.get("pr_number", -1)) == pr_number:
            row = obj
            break
    if row is None:
        raise ValueError(f"pr not found in per_pr.jsonl: {pr_number}")

    routers = row.get("routers") or row.get("baselines") or {}
    if not isinstance(routers, dict) or not routers:
        raise ValueError("missing routers for pr")

    chosen = router or baseline
    if chosen is None:
        chosen = sorted(routers.keys(), key=lambda s: str(s).lower())[0]
    if chosen not in routers:
        raise ValueError(f"router not found: {chosen}")

    selected_policy = policy
    truth_block = row.get("truth")
    truth_policies = {}
    if isinstance(truth_block, dict):
        raw = truth_block.get("policies")
        if isinstance(raw, dict):
            truth_policies = raw
            if selected_policy is None:
                raw_primary = truth_block.get("primary_policy")
                if isinstance(raw_primary, str) and raw_primary.strip():
                    selected_policy = raw_primary.strip()
    if selected_policy is None and truth_policies:
        selected_policy = sorted(truth_policies.keys(), key=lambda s: str(s).lower())[0]
    if selected_policy is not None and truth_policies and selected_policy not in truth_policies:
        raise ValueError(f"truth policy not found: {selected_policy}")

    lines: list[str] = []
    lines.append(f"repo {repo}")
    lines.append(f"run_id {run_id}")
    lines.append(f"pr {pr_number}")
    lines.append(f"cutoff {row.get('cutoff')}")
    lines.append(f"router {chosen}")
    if selected_policy is not None:
        lines.append(f"truth_policy {selected_policy}")
    lines.append("")

    lines.append("truth_behavior")
    if selected_policy is not None and truth_policies:
        targets = (truth_policies.get(selected_policy) or {}).get("targets") or []
    else:
        targets = row.get("truth_behavior") or []
    for t in targets:
        lines.append(f"- {t}")
    if selected_policy is not None and truth_policies:
        policy_entry = truth_policies.get(selected_policy) or {}
        lines.append(f"- status: {policy_entry.get('status')}")
    lines.append("")

    b = routers[chosen]
    rr = b.get("route_result") or {}
    lines.append("candidates")
    for c in rr.get("candidates") or []:
        target = (c.get("target") or {}).get("name")
        score = c.get("score")
        lines.append(f"- {target} (score={score})")
        for ev in c.get("evidence") or []:
            kind = ev.get("kind")
            data = ev.get("data")
            lines.append(f"  {kind}: {data}")
    lines.append("")

    lines.append("routing_agreement")
    routing_agreement = b.get("routing_agreement") or {}
    by_policy = b.get("routing_agreement_by_policy")
    if (
        selected_policy is not None
        and isinstance(by_policy, dict)
        and isinstance(by_policy.get(selected_policy), dict)
    ):
        routing_agreement = by_policy.get(selected_policy) or {}
    lines.append(
        json.dumps(
            routing_agreement,
            sort_keys=True,
            indent=2,
            ensure_ascii=True,
        )
    )
    lines.append("")

    lines.append("gates")
    lines.append(
        json.dumps(row.get("gates") or {}, sort_keys=True, indent=2, ensure_ascii=True)
    )
    lines.append("")

    lines.append("queue")
    lines.append(json.dumps(b.get("queue") or {}, sort_keys=True, indent=2, ensure_ascii=True))

    return "\n".join(lines)
