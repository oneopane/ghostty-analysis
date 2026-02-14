from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .reporting.formatters import json_dumps


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def _parse_dt(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    s = str(value)
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
    except Exception:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _iso_utc(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    normalized = dt.astimezone(timezone.utc)
    return normalized.isoformat().replace("+00:00", "Z")


def _min_max_cutoffs(
    *, pr_cutoffs: dict[str, object] | None
) -> tuple[str | None, str | None]:
    if not pr_cutoffs:
        return None, None
    dts: list[datetime] = []
    for raw in pr_cutoffs.values():
        dt = _parse_dt(raw)
        if dt is not None:
            dts.append(dt)
    if not dts:
        return None, None
    dts.sort()
    return _iso_utc(dts[0]), _iso_utc(dts[-1])


def _count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    n = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                n += 1
    return n


def build_run_summary(*, repo: str, run_id: str, run_dir: Path) -> dict[str, Any]:
    manifest_path = run_dir / "manifest.json"
    report_path = run_dir / "report.json"
    report_md_path = run_dir / "report.md"
    per_pr_path = run_dir / "per_pr.jsonl"
    exp_manifest_path = run_dir / "experiment_manifest.json"
    cohort_path = run_dir / "cohort.json"
    spec_path = run_dir / "experiment.json"

    manifest = _read_json(manifest_path) or {}
    report = _read_json(report_path) or {}
    exp_manifest = _read_json(exp_manifest_path) or {}
    cohort = _read_json(cohort_path) or {}
    spec = _read_json(spec_path) or {}

    watermark = {
        "db_max_event_occurred_at": (
            manifest.get("db_max_event_occurred_at")
            if manifest.get("db_max_event_occurred_at") is not None
            else report.get("db_max_event_occurred_at")
        ),
        "db_max_watermark_updated_at": (
            manifest.get("db_max_watermark_updated_at")
            if manifest.get("db_max_watermark_updated_at") is not None
            else report.get("db_max_watermark_updated_at")
        ),
        "cutoff_source": (
            exp_manifest.get("cutoff_source")
            if isinstance(exp_manifest.get("cutoff_source"), str)
            else manifest.get("cutoff_source")
        ),
        "cutoff_policy": None,
        "min_pr_cutoff": None,
        "max_pr_cutoff": None,
    }
    cfg = manifest.get("config") if isinstance(manifest.get("config"), dict) else {}
    defaults = cfg.get("defaults") if isinstance(cfg.get("defaults"), dict) else {}
    cutoff_policy = defaults.get("cutoff_policy")
    watermark["cutoff_policy"] = (
        str(cutoff_policy) if isinstance(cutoff_policy, str) else None
    )

    llm_mode = defaults.get("llm_mode")
    llm_mode_out = str(llm_mode).strip().lower() if isinstance(llm_mode, str) else None

    pr_cutoffs = None
    if isinstance(manifest.get("pr_cutoffs"), dict):
        pr_cutoffs = manifest.get("pr_cutoffs")
    elif isinstance(exp_manifest.get("pr_cutoffs"), dict):
        pr_cutoffs = exp_manifest.get("pr_cutoffs")
    watermark["min_pr_cutoff"], watermark["max_pr_cutoff"] = _min_max_cutoffs(
        pr_cutoffs=pr_cutoffs
    )

    routers: list[str] = []
    if isinstance(report.get("routers"), list):
        routers = [str(x) for x in report.get("routers") if str(x).strip()]
    elif isinstance(exp_manifest.get("routers"), list):
        routers = [str(x) for x in exp_manifest.get("routers") if str(x).strip()]
    elif isinstance(manifest.get("routers"), list):
        for item in manifest.get("routers"):
            if isinstance(item, dict) and isinstance(item.get("router_id"), str):
                routers.append(item.get("router_id"))
    routers = sorted(set(routers), key=lambda s: s.lower())

    artifact_prefetch_raw = exp_manifest.get("artifact_prefetch")
    artifact_prefetch = (
        artifact_prefetch_raw if isinstance(artifact_prefetch_raw, dict) else {}
    )
    events = (
        artifact_prefetch.get("events")
        if isinstance(artifact_prefetch.get("events"), list)
        else []
    )
    artifact_prefetch_out: dict[str, object] | None = None
    if artifact_prefetch:
        artifact_prefetch_out = {
            "enabled": (
                artifact_prefetch.get("enabled")
                if isinstance(artifact_prefetch.get("enabled"), bool)
                else None
            ),
            "network_used": (
                artifact_prefetch.get("network_used")
                if isinstance(artifact_prefetch.get("network_used"), bool)
                else None
            ),
            "requested_artifact_paths": (
                artifact_prefetch.get("requested_artifact_paths")
                if isinstance(artifact_prefetch.get("requested_artifact_paths"), list)
                else []
            ),
            "event_count": len(events),
        }

    report_extra = report.get("extra") if isinstance(report.get("extra"), dict) else {}
    truth_primary_policy = report_extra.get("truth_primary_policy")
    if not isinstance(truth_primary_policy, str) or not truth_primary_policy.strip():
        truth_primary_policy = None

    truth_coverage_counts = (
        report_extra.get("truth_coverage_counts")
        if isinstance(report_extra.get("truth_coverage_counts"), dict)
        else {}
    )
    truth_coverage_counts_clean: dict[str, int] = {}
    for k, v in truth_coverage_counts.items():
        if isinstance(k, str) and isinstance(v, (int, float)):
            truth_coverage_counts_clean[k] = int(v)

    routing_agreement = report.get("routing_agreement")
    routing_agreement_clean: dict[str, dict[str, object]] = {}
    if isinstance(routing_agreement, dict):
        for rid, payload in routing_agreement.items():
            if not isinstance(rid, str) or not isinstance(payload, dict):
                continue
            routing_agreement_clean[rid] = {
                "n": int(payload.get("n") or 0),
                "mrr": payload.get("mrr")
                if isinstance(payload.get("mrr"), (int, float))
                else None,
                "hit_at_1": (
                    payload.get("hit_at_1")
                    if isinstance(payload.get("hit_at_1"), (int, float))
                    else None
                ),
                "hit_at_3": (
                    payload.get("hit_at_3")
                    if isinstance(payload.get("hit_at_3"), (int, float))
                    else None
                ),
                "hit_at_5": (
                    payload.get("hit_at_5")
                    if isinstance(payload.get("hit_at_5"), (int, float))
                    else None
                ),
            }

    worst_slices: list[dict[str, object]] = []
    slices_by_policy = (
        report_extra.get("routing_agreement_slices_by_policy")
        if isinstance(report_extra.get("routing_agreement_slices_by_policy"), dict)
        else None
    )
    policy_for_slices: str | None = truth_primary_policy
    if (
        policy_for_slices is None
        and isinstance(slices_by_policy, dict)
        and slices_by_policy
    ):
        policy_for_slices = sorted(
            [str(k) for k in slices_by_policy.keys() if str(k).strip()],
            key=lambda s: s.lower(),
        )[0]
    if policy_for_slices is not None and isinstance(slices_by_policy, dict):
        by_router = slices_by_policy.get(policy_for_slices)
        if isinstance(by_router, dict):
            for rid, by_slice in by_router.items():
                if not isinstance(rid, str) or not isinstance(by_slice, dict):
                    continue
                for slice_name, metrics in by_slice.items():
                    if not isinstance(metrics, dict):
                        continue
                    n = metrics.get("n")
                    mrr = metrics.get("mrr")
                    if not isinstance(n, (int, float)) or int(n) <= 0:
                        continue
                    if not isinstance(mrr, (int, float)):
                        continue
                    worst_slices.append(
                        {
                            "policy_id": policy_for_slices,
                            "router_id": rid,
                            "slice": str(slice_name),
                            "n": int(n),
                            "mrr": float(mrr),
                            "hit_at_1": (
                                float(metrics.get("hit_at_1"))
                                if isinstance(metrics.get("hit_at_1"), (int, float))
                                else None
                            ),
                        }
                    )
    worst_slices.sort(
        key=lambda r: (
            float(r.get("mrr") or 0.0),
            -int(r.get("n") or 0),
            str(r.get("router_id") or "").lower(),
            str(r.get("slice") or "").lower(),
        )
    )
    worst_slices = worst_slices[:20]

    llm_total_cost = None
    llm_telemetry = report_extra.get("llm_telemetry")
    if isinstance(llm_telemetry, dict):
        cost = llm_telemetry.get("total_cost_usd")
        if isinstance(cost, (int, float)):
            llm_total_cost = float(cost)

    cohort_hash = exp_manifest.get("cohort_hash")
    if not isinstance(cohort_hash, str) or not cohort_hash.strip():
        cohort_hash = cohort.get("hash")
    cohort_hash_out = (
        str(cohort_hash)
        if isinstance(cohort_hash, str) and cohort_hash.strip()
        else None
    )

    spec_hash = exp_manifest.get("experiment_spec_hash")
    if not isinstance(spec_hash, str) or not spec_hash.strip():
        spec_hash = spec.get("hash")
    spec_hash_out = (
        str(spec_hash) if isinstance(spec_hash, str) and spec_hash.strip() else None
    )

    pr_count = 0
    manifest_prs = manifest.get("pr_numbers")
    if isinstance(manifest_prs, list):
        try:
            pr_count = len([int(x) for x in manifest_prs])
        except Exception:
            pr_count = len(manifest_prs)

    per_pr_row_count = _count_jsonl_rows(per_pr_path)
    if pr_count <= 0:
        pr_count = per_pr_row_count

    def rel_or_none(p: Path) -> str | None:
        return p.name if p.exists() else None

    artifacts = {
        "manifest_json": rel_or_none(manifest_path),
        "report_json": rel_or_none(report_path),
        "report_md": rel_or_none(report_md_path),
        "per_pr_jsonl": rel_or_none(per_pr_path),
        "experiment_manifest_json": rel_or_none(exp_manifest_path),
        "cohort_json": rel_or_none(cohort_path),
        "experiment_json": rel_or_none(spec_path),
    }

    def sha_or_none(p: Path) -> str | None:
        return _sha256_file(p) if p.exists() else None

    hashes = {
        "manifest_json_sha256": sha_or_none(manifest_path),
        "report_json_sha256": sha_or_none(report_path),
        "per_pr_jsonl_sha256": sha_or_none(per_pr_path),
        "experiment_manifest_json_sha256": sha_or_none(exp_manifest_path),
        "cohort_json_sha256": sha_or_none(cohort_path),
        "experiment_json_sha256": sha_or_none(spec_path),
    }

    warnings: list[str] = []
    notes = report.get("notes") if isinstance(report.get("notes"), list) else []
    for item in notes:
        s = str(item).strip()
        if s:
            warnings.append(s)
    warnings = sorted(set(warnings), key=lambda s: s.lower())

    quality_gates = (
        report_extra.get("quality_gates") if isinstance(report_extra, dict) else None
    )
    promotion_evaluation = (
        report_extra.get("promotion_evaluation")
        if isinstance(report_extra, dict)
        else None
    )

    actionable_failures: list[dict[str, object]] = []
    gate_category = {
        "G1_truth_window_consistency": "cutoff_safety",
        "G2_truth_policy_schema": "data_integrity",
        "G3_unknown_ingestion_gap_rate": "truth_coverage",
        "G4_ownership_availability": "data_integrity",
        "G5_router_unavailable_rate": "performance",
        "G6_deterministic_reproducibility": "stability",
    }

    def record_failure(
        *, gate_id: str, category: str, reason: str, inspect: dict[str, str]
    ) -> None:
        actionable_failures.append(
            {
                "gate_id": gate_id,
                "category": category,
                "pass": False,
                "reason": reason,
                "inspect": inspect,
            }
        )

    if isinstance(quality_gates, dict):
        gates_block = quality_gates.get("gates")
        if isinstance(gates_block, dict):
            for gate_id in sorted(gates_block.keys(), key=lambda s: str(s).lower()):
                payload = gates_block.get(gate_id)
                if not isinstance(payload, dict):
                    continue
                passed = payload.get("pass")
                if passed is not False:
                    continue

                category = gate_category.get(str(gate_id), "unknown")
                reason = f"{gate_id} failed"
                if gate_id == "G4_ownership_availability":
                    reason = "repo_profile coverage missing CODEOWNERS for some PRs"
                elif gate_id == "G5_router_unavailable_rate":
                    reason = "router output missing or invalid for some PRs"
                elif gate_id == "G3_unknown_ingestion_gap_rate":
                    reason = "truth unknown due to ingestion gaps for some PRs"
                elif gate_id == "G6_deterministic_reproducibility":
                    reason = "determinism check failed (multiple hashes observed)"
                elif gate_id == "G1_truth_window_consistency":
                    reason = "truth window does not align with cutoff for some PRs"
                elif gate_id == "G2_truth_policy_schema":
                    reason = "truth policy payload schema is missing required fields"

                inspect = {
                    "report_json": "report.json",
                    "per_pr_jsonl": "per_pr.jsonl",
                }
                if gate_id == "G4_ownership_availability":
                    inspect["repo_profile_dir_template"] = (
                        "prs/{pr_number}/repo_profile/"
                    )
                if gate_id in {
                    "G5_router_unavailable_rate",
                    "G6_deterministic_reproducibility",
                }:
                    inspect["route_template"] = (
                        "prs/{pr_number}/routes/{router_id}.json"
                    )
                if gate_id in {
                    "G1_truth_window_consistency",
                    "G3_unknown_ingestion_gap_rate",
                }:
                    inspect["truth_diagnostics_field"] = "truth_diagnostics"

                record_failure(
                    gate_id=str(gate_id),
                    category=category,
                    reason=reason,
                    inspect=inspect,
                )

    # Stale-cutoff notes are produced when strict_streaming_eval is disabled.
    for note in warnings:
        if note.startswith("db_max_event_occurred_at=") and "is before cutoffs" in note:
            record_failure(
                gate_id="EVAL_stale_cutoff_horizon",
                category="cutoff_safety",
                reason=note,
                inspect={
                    "manifest_json": "manifest.json",
                    "report_json": "report.json",
                },
            )

    summary: dict[str, Any] = {
        "schema_version": 1,
        "kind": "run_summary",
        "repo": repo,
        "run_id": run_id,
        "watermark": watermark,
        "inputs": {
            "cohort_hash": cohort_hash_out,
            "experiment_spec_hash": spec_hash_out,
            "routers": routers,
            "truth_primary_policy": truth_primary_policy,
            "llm_mode": llm_mode_out,
            "artifact_prefetch": artifact_prefetch_out,
        },
        "counts": {
            "pr_count": int(pr_count),
            "per_pr_row_count": int(per_pr_row_count),
        },
        "artifacts": artifacts,
        "hashes": hashes,
        "headline_metrics": {
            "routing_agreement": {
                k: routing_agreement_clean[k]
                for k in sorted(routing_agreement_clean.keys(), key=lambda s: s.lower())
            },
            "llm_total_cost_usd": llm_total_cost,
            "worst_slices": worst_slices,
        },
        "gates": {
            "truth_coverage_counts": {
                k: truth_coverage_counts_clean[k]
                for k in sorted(
                    truth_coverage_counts_clean.keys(), key=lambda s: s.lower()
                )
            },
            "gate_correlation": report.get("gates")
            if isinstance(report.get("gates"), dict)
            else None,
            "quality_gates": quality_gates if isinstance(quality_gates, dict) else None,
            "promotion_evaluation": (
                promotion_evaluation if isinstance(promotion_evaluation, dict) else None
            ),
            "warnings": warnings,
            "taxonomy": {
                "version": "v1",
                "categories": [
                    "data_integrity",
                    "cutoff_safety",
                    "truth_coverage",
                    "performance",
                    "stability",
                ],
            },
            "failures": sorted(
                actionable_failures,
                key=lambda f: (
                    str(f.get("category") or "").lower(),
                    str(f.get("gate_id") or "").lower(),
                ),
            ),
        },
        "drill": {
            "prs_dir": "prs",
            "pr_dir_template": "prs/{pr_number}",
            "snapshot_template": "prs/{pr_number}/snapshot.json",
            "inputs_template": "prs/{pr_number}/inputs.json",
            "route_template": "prs/{pr_number}/routes/{router_id}.json",
            "per_pr_jsonl": "per_pr.jsonl",
            "report_json": "report.json",
        },
    }

    # Additive, optional convenience fields.
    generated_at = manifest.get("generated_at")
    if generated_at is None:
        generated_at = report.get("generated_at")
    summary["generated_at"] = generated_at
    summary["package_versions"] = (
        manifest.get("package_versions")
        if isinstance(manifest.get("package_versions"), dict)
        else {}
    )
    return summary


def write_run_summary(*, repo: str, run_id: str, run_dir: Path) -> Path:
    payload = build_run_summary(repo=repo, run_id=run_id, run_dir=run_dir)
    out = run_dir / "run_summary.json"
    out.write_text(json_dumps(payload), encoding="utf-8")
    return out


__all__ = ["build_run_summary", "write_run_summary"]
