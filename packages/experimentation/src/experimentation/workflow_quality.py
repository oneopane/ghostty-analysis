from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from evaluation_harness.paths import eval_report_json_path, eval_report_md_path
from repo_routing.time import parse_dt_utc

from .workflow_helpers import _write_json

_POST_PROCESSING_START = "<!-- experiment-post-processing:start -->"
_POST_PROCESSING_END = "<!-- experiment-post-processing:end -->"


def _safe_ratio(numer: int, denom: int) -> float:
    if denom <= 0:
        return 0.0
    return float(numer) / float(denom)


def _quality_thresholds(*, routers: list[str]) -> dict[str, float]:
    phase2_like = any(r in {"union", "hybrid_ranker", "llm_rerank"} for r in routers)
    if phase2_like:
        return {
            "unknown_max": 0.02,
            "availability_min": 0.95,
            "unavailable_max": 0.01,
        }
    return {
        "unknown_max": 0.03,
        "availability_min": 0.90,
        "unavailable_max": 0.02,
    }


def evaluate_quality_gates(
    *,
    rows: list[dict[str, Any]],
    report: dict[str, Any],
    routers: list[str],
) -> dict[str, Any]:
    thresholds = _quality_thresholds(routers=routers)

    extra = report.get("extra") if isinstance(report.get("extra"), dict) else {}
    truth_counts_raw = (
        extra.get("truth_coverage_counts") if isinstance(extra, dict) else {}
    )
    truth_counts = truth_counts_raw if isinstance(truth_counts_raw, dict) else {}
    total_truth = sum(
        int(v) for v in truth_counts.values() if isinstance(v, (int, float))
    )
    unknown_n = int(truth_counts.get("unknown_due_to_ingestion_gap", 0))
    unknown_rate = _safe_ratio(unknown_n, total_truth if total_truth > 0 else len(rows))

    profile_rows = [r for r in rows if isinstance(r.get("repo_profile"), dict)]
    codeowners_present = 0
    for row in profile_rows:
        coverage = (row.get("repo_profile") or {}).get("coverage")
        if isinstance(coverage, dict) and bool(coverage.get("codeowners_present")):
            codeowners_present += 1
    availability = _safe_ratio(codeowners_present, len(profile_rows))

    unavailable_slots = 0
    total_slots = 0
    for row in rows:
        by_router = row.get("routers")
        if not isinstance(by_router, dict):
            continue
        for rid in routers:
            payload = by_router.get(rid)
            if not isinstance(payload, dict):
                continue
            total_slots += 1
            route_result = payload.get("route_result")
            if not isinstance(route_result, dict):
                unavailable_slots += 1
                continue
            candidates = route_result.get("candidates")
            if not isinstance(candidates, list) or not candidates:
                unavailable_slots += 1
    unavailable_rate = _safe_ratio(unavailable_slots, total_slots)

    window_consistent_n = 0
    window_total_n = 0
    for row in rows:
        diag = row.get("truth_diagnostics")
        cutoff_raw = row.get("cutoff")
        if not isinstance(diag, dict) or not isinstance(cutoff_raw, str):
            continue
        end_raw = diag.get("window_end")
        if not isinstance(end_raw, str):
            continue
        try:
            cutoff = parse_dt_utc(cutoff_raw)
            end = parse_dt_utc(end_raw)
        except Exception:
            continue
        if cutoff is None or end is None:
            continue
        window_total_n += 1
        if end > cutoff:
            window_consistent_n += 1
    window_consistency = _safe_ratio(window_consistent_n, window_total_n)

    g2_ok = True
    for row in rows:
        truth = row.get("truth")
        if not isinstance(truth, dict):
            continue
        policies = truth.get("policies")
        if not isinstance(policies, dict):
            g2_ok = False
            break
        for _, payload in policies.items():
            if not isinstance(payload, dict):
                g2_ok = False
                break
            if "status" not in payload or "diagnostics" not in payload:
                g2_ok = False
                break
        if not g2_ok:
            break

    deterministic_ok = True
    hybrid_hashes: set[str] = set()
    for row in rows:
        by_router = row.get("routers")
        if not isinstance(by_router, dict):
            continue
        payload = by_router.get("hybrid_ranker")
        if not isinstance(payload, dict):
            continue
        route_result = payload.get("route_result")
        if not isinstance(route_result, dict):
            continue
        notes = route_result.get("notes")
        if not isinstance(notes, list):
            continue
        for note in notes:
            s = str(note)
            if s.startswith("weights_hash="):
                hybrid_hashes.add(s[len("weights_hash="):])
    if len(hybrid_hashes) > 1:
        deterministic_ok = False

    gates = {
        "G1_truth_window_consistency": {
            "value": window_consistency,
            "target": 1.0,
            "pass": window_consistency >= 1.0,
        },
        "G2_truth_policy_schema": {"pass": g2_ok},
        "G3_unknown_ingestion_gap_rate": {
            "value": unknown_rate,
            "max": thresholds["unknown_max"],
            "pass": unknown_rate <= thresholds["unknown_max"],
        },
        "G4_ownership_availability": {
            "value": availability,
            "min": thresholds["availability_min"],
            "pass": availability >= thresholds["availability_min"],
        },
        "G5_router_unavailable_rate": {
            "value": unavailable_rate,
            "max": thresholds["unavailable_max"],
            "pass": unavailable_rate <= thresholds["unavailable_max"],
        },
        "G6_deterministic_reproducibility": {
            "pass": deterministic_ok,
            "hybrid_weights_hashes": sorted(hybrid_hashes),
        },
    }
    all_pass = all(bool(v.get("pass")) for v in gates.values())
    return {
        "thresholds": thresholds,
        "gates": gates,
        "all_pass": all_pass,
    }


def _bootstrap_delta(
    *,
    values: list[float],
    samples: int = 500,
    seed: int = 42,
) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    rng = random.Random(seed)
    means: list[float] = []
    n = len(values)
    for _ in range(samples):
        draw = [values[rng.randrange(0, n)] for _ in range(n)]
        means.append(sum(draw) / float(n))
    means.sort()
    lo_idx = int(0.025 * (len(means) - 1))
    hi_idx = int(0.975 * (len(means) - 1))
    return means[lo_idx], means[hi_idx]


def evaluate_promotion(
    *,
    rows: list[dict[str, Any]],
    routers: list[str],
    primary_policy: str,
    gate_all_pass: bool,
) -> dict[str, Any]:
    baseline: str | None = None
    candidate: str | None = None
    if "hybrid_ranker" in routers and "popularity" in routers:
        baseline, candidate = "popularity", "hybrid_ranker"
    elif "union" in routers and "popularity" in routers:
        baseline, candidate = "popularity", "union"
    elif "llm_rerank" in routers and "hybrid_ranker" in routers:
        baseline, candidate = "hybrid_ranker", "llm_rerank"
    if baseline is None or candidate is None:
        return {
            "eligible": False,
            "reason": "missing comparable router pair",
            "primary_policy": primary_policy,
        }

    deltas_mrr: list[float] = []
    deltas_hit1: list[float] = []
    for row in rows:
        truth = row.get("truth")
        if not isinstance(truth, dict):
            continue
        policies = truth.get("policies")
        if not isinstance(policies, dict):
            continue
        policy_row = policies.get(primary_policy)
        if not isinstance(policy_row, dict):
            continue
        if str(policy_row.get("status") or "") != "observed":
            continue

        routers_payload = row.get("routers")
        if not isinstance(routers_payload, dict):
            continue
        base_row = routers_payload.get(baseline)
        cand_row = routers_payload.get(candidate)
        if not isinstance(base_row, dict) or not isinstance(cand_row, dict):
            continue

        base_route = base_row.get("route_result")
        cand_route = cand_row.get("route_result")
        if not isinstance(base_route, dict) or not isinstance(cand_route, dict):
            continue
        if not isinstance(base_route.get("candidates"), list) or not base_route.get("candidates"):
            continue
        if not isinstance(cand_route.get("candidates"), list) or not cand_route.get("candidates"):
            continue

        base_metrics = (base_row.get("routing_agreement_by_policy") or {}).get(primary_policy)
        cand_metrics = (cand_row.get("routing_agreement_by_policy") or {}).get(primary_policy)
        if not isinstance(base_metrics, dict) or not isinstance(cand_metrics, dict):
            continue
        base_mrr = base_metrics.get("mrr")
        cand_mrr = cand_metrics.get("mrr")
        base_hit1 = base_metrics.get("hit_at_1")
        cand_hit1 = cand_metrics.get("hit_at_1")
        if not isinstance(base_mrr, (int, float)) or not isinstance(cand_mrr, (int, float)):
            continue
        if not isinstance(base_hit1, (int, float)) or not isinstance(cand_hit1, (int, float)):
            continue
        deltas_mrr.append(float(cand_mrr) - float(base_mrr))
        deltas_hit1.append(float(cand_hit1) - float(base_hit1))

    n = len(deltas_mrr)
    delta_mrr = sum(deltas_mrr) / float(n) if n > 0 else 0.0
    ci_lo, ci_hi = _bootstrap_delta(values=deltas_mrr)
    delta_hit1 = sum(deltas_hit1) / float(len(deltas_hit1)) if deltas_hit1 else 0.0
    pass_rule = (
        n >= 120
        and delta_mrr >= 0.015
        and ci_lo > 0.0
        and gate_all_pass
        and delta_hit1 >= -0.01
    )
    return {
        "eligible": True,
        "primary_policy": primary_policy,
        "baseline_router": baseline,
        "candidate_router": candidate,
        "n_observed_and_router_nonempty": n,
        "delta_mrr": delta_mrr,
        "delta_mrr_bootstrap_ci95": [ci_lo, ci_hi],
        "delta_hit_at_1": delta_hit1,
        "gates_pass": gate_all_pass,
        "promote": pass_rule,
    }


def _render_post_processing_block(
    *,
    quality_gates: dict[str, Any],
    promotion_evaluation: dict[str, Any],
) -> str:
    payload = {
        "quality_gates": quality_gates,
        "promotion_evaluation": promotion_evaluation,
    }
    body = json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2)
    return (
        f"{_POST_PROCESSING_START}\n"
        "## Experiment Post-Processing\n\n"
        "```json\n"
        f"{body}\n"
        "```\n"
        f"{_POST_PROCESSING_END}\n"
    )


def _upsert_post_processing_markdown(*, md_text: str, block: str) -> str:
    start = md_text.find(_POST_PROCESSING_START)
    end = md_text.find(_POST_PROCESSING_END)
    if start != -1 and end != -1 and end > start:
        end += len(_POST_PROCESSING_END)
        before = md_text[:start].rstrip()
        if before:
            before += "\n\n"
        return before + block
    stripped = md_text.rstrip()
    if stripped:
        return stripped + "\n\n" + block
    return block


def persist_report_post_processing(
    *,
    repo: str,
    run_id: str,
    data_dir: str,
    report_payload: dict[str, Any],
    quality_gates: dict[str, Any],
    promotion_evaluation: dict[str, Any],
) -> dict[str, Any]:
    report_extra = report_payload.get("extra")
    if not isinstance(report_extra, dict):
        report_extra = {}
    report_extra["quality_gates"] = quality_gates
    report_extra["promotion_evaluation"] = promotion_evaluation
    report_payload["extra"] = report_extra

    report_json = eval_report_json_path(
        repo_full_name=repo,
        data_dir=data_dir,
        run_id=run_id,
    )
    _write_json(report_json, report_payload)

    md_path = eval_report_md_path(
        repo_full_name=repo,
        data_dir=data_dir,
        run_id=run_id,
    )
    current_md = ""
    if md_path.exists():
        current_md = md_path.read_text(encoding="utf-8")
    block = _render_post_processing_block(
        quality_gates=quality_gates,
        promotion_evaluation=promotion_evaluation,
    )
    updated_md = _upsert_post_processing_markdown(md_text=current_md, block=block)
    md_path.write_text(updated_md.rstrip() + "\n", encoding="utf-8")
    return report_payload
