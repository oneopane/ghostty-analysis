from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import repo_eval_dir, repo_eval_run_dir
from .reporting.formatters import json_dumps
from .run_summary import build_run_summary, write_run_summary


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stable_json_compact(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _sha256_json(obj: object) -> str:
    return _sha256_text(_stable_json_compact(obj))


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def _read_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _rel_under_data_dir(path: Path, *, data_dir: str) -> str:
    try:
        return path.relative_to(Path(data_dir)).as_posix()
    except Exception:
        return path.as_posix()


def _pr_cutoffs_hash(run_dir: Path) -> str | None:
    manifest = _read_json(run_dir / "manifest.json")
    if isinstance(manifest, dict) and isinstance(manifest.get("pr_cutoffs"), dict):
        return _sha256_json(manifest.get("pr_cutoffs"))

    exp_manifest = _read_json(run_dir / "experiment_manifest.json")
    if isinstance(exp_manifest, dict) and isinstance(
        exp_manifest.get("pr_cutoffs"), dict
    ):
        return _sha256_json(exp_manifest.get("pr_cutoffs"))

    return None


def _truth_coverage_counts(summary: dict[str, Any]) -> dict[str, int]:
    gates = summary.get("gates") if isinstance(summary.get("gates"), dict) else {}
    counts = (
        gates.get("truth_coverage_counts")
        if isinstance(gates.get("truth_coverage_counts"), dict)
        else {}
    )
    out: dict[str, int] = {}
    for k, v in counts.items():
        if isinstance(k, str) and isinstance(v, (int, float)):
            out[k] = int(v)
    return out


def _get_quality_gate_block(summary: dict[str, Any]) -> dict[str, Any] | None:
    gates = summary.get("gates") if isinstance(summary.get("gates"), dict) else {}
    q = gates.get("quality_gates")
    return q if isinstance(q, dict) else None


def _get_promotion_block(summary: dict[str, Any]) -> dict[str, Any] | None:
    gates = summary.get("gates") if isinstance(summary.get("gates"), dict) else {}
    p = gates.get("promotion_evaluation")
    return p if isinstance(p, dict) else None


def _router_metrics(summary: dict[str, Any]) -> dict[str, dict[str, object]]:
    headline = (
        summary.get("headline_metrics")
        if isinstance(summary.get("headline_metrics"), dict)
        else {}
    )
    routing = (
        headline.get("routing_agreement")
        if isinstance(headline.get("routing_agreement"), dict)
        else {}
    )
    out: dict[str, dict[str, object]] = {}
    for rid, payload in routing.items():
        if not isinstance(rid, str) or not isinstance(payload, dict):
            continue
        out[rid] = dict(payload)
    return out


def _delta_number(a: object, b: object) -> float | None:
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return None
    return float(b) - float(a)


def _ranked_router_deltas(
    *,
    baseline: dict[str, dict[str, object]],
    candidate: dict[str, dict[str, object]],
) -> list[dict[str, Any]]:
    common = sorted(
        set(baseline.keys()) & set(candidate.keys()), key=lambda s: s.lower()
    )
    rows: list[dict[str, Any]] = []
    for rid in common:
        b = baseline.get(rid) or {}
        c = candidate.get(rid) or {}
        row = {
            "router_id": rid,
            "baseline": {
                "n": int(b.get("n") or 0),
                "mrr": b.get("mrr"),
                "hit_at_1": b.get("hit_at_1"),
                "hit_at_3": b.get("hit_at_3"),
                "hit_at_5": b.get("hit_at_5"),
            },
            "candidate": {
                "n": int(c.get("n") or 0),
                "mrr": c.get("mrr"),
                "hit_at_1": c.get("hit_at_1"),
                "hit_at_3": c.get("hit_at_3"),
                "hit_at_5": c.get("hit_at_5"),
            },
            "delta": {
                "mrr": _delta_number(b.get("mrr"), c.get("mrr")),
                "hit_at_1": _delta_number(b.get("hit_at_1"), c.get("hit_at_1")),
                "hit_at_3": _delta_number(b.get("hit_at_3"), c.get("hit_at_3")),
                "hit_at_5": _delta_number(b.get("hit_at_5"), c.get("hit_at_5")),
            },
        }
        rows.append(row)

    def key(r: dict[str, Any]) -> tuple[float, str]:
        d = (r.get("delta") or {}).get("mrr")
        dmrr = float(d) if isinstance(d, (int, float)) else 0.0
        return (dmrr, str(r.get("router_id") or "").lower())

    rows.sort(key=key)
    return rows


def _slice_deltas(
    *,
    baseline_report: dict[str, Any],
    candidate_report: dict[str, Any],
    limit: int = 20,
) -> list[dict[str, Any]]:
    b_extra = (
        baseline_report.get("extra")
        if isinstance(baseline_report.get("extra"), dict)
        else {}
    )
    c_extra = (
        candidate_report.get("extra")
        if isinstance(candidate_report.get("extra"), dict)
        else {}
    )

    b_slices = b_extra.get("routing_agreement_slices_by_policy")
    c_slices = c_extra.get("routing_agreement_slices_by_policy")
    if not isinstance(b_slices, dict) or not isinstance(c_slices, dict):
        return []

    rows: list[dict[str, Any]] = []
    common_policies = sorted(
        set(b_slices.keys()) & set(c_slices.keys()), key=lambda s: str(s).lower()
    )
    for pid in common_policies:
        b_by_router = b_slices.get(pid)
        c_by_router = c_slices.get(pid)
        if not isinstance(b_by_router, dict) or not isinstance(c_by_router, dict):
            continue
        common_routers = sorted(
            set(b_by_router.keys()) & set(c_by_router.keys()),
            key=lambda s: str(s).lower(),
        )
        for rid in common_routers:
            b_by_slice = b_by_router.get(rid)
            c_by_slice = c_by_router.get(rid)
            if not isinstance(b_by_slice, dict) or not isinstance(c_by_slice, dict):
                continue
            common_slices = sorted(
                set(b_by_slice.keys()) & set(c_by_slice.keys()),
                key=lambda s: str(s).lower(),
            )
            for slice_name in common_slices:
                b_metrics = b_by_slice.get(slice_name)
                c_metrics = c_by_slice.get(slice_name)
                if not isinstance(b_metrics, dict) or not isinstance(c_metrics, dict):
                    continue
                dmrr = _delta_number(b_metrics.get("mrr"), c_metrics.get("mrr"))
                if dmrr is None or dmrr >= 0.0:
                    continue
                rows.append(
                    {
                        "policy_id": str(pid),
                        "router_id": str(rid),
                        "slice": str(slice_name),
                        "baseline": {
                            "n": int(b_metrics.get("n") or 0),
                            "mrr": b_metrics.get("mrr"),
                            "hit_at_1": b_metrics.get("hit_at_1"),
                        },
                        "candidate": {
                            "n": int(c_metrics.get("n") or 0),
                            "mrr": c_metrics.get("mrr"),
                            "hit_at_1": c_metrics.get("hit_at_1"),
                        },
                        "delta": {
                            "mrr": dmrr,
                            "hit_at_1": _delta_number(
                                b_metrics.get("hit_at_1"), c_metrics.get("hit_at_1")
                            ),
                        },
                    }
                )

    rows.sort(
        key=lambda r: (
            float((r.get("delta") or {}).get("mrr") or 0.0),
            str(r.get("policy_id") or "").lower(),
            str(r.get("router_id") or "").lower(),
            str(r.get("slice") or "").lower(),
        )
    )
    return rows[: max(0, int(limit))]


def _top_regressed_examples(
    *,
    baseline_run_id: str,
    candidate_run_id: str,
    baseline_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    policy_id: str | None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    b_by_pr = {
        int(r.get("pr_number")): r
        for r in baseline_rows
        if isinstance(r.get("pr_number"), int)
    }
    c_by_pr = {
        int(r.get("pr_number")): r
        for r in candidate_rows
        if isinstance(r.get("pr_number"), int)
    }
    shared_prs = sorted(set(b_by_pr.keys()) & set(c_by_pr.keys()))
    if not shared_prs:
        return []

    out: list[dict[str, Any]] = []
    for pr in shared_prs:
        br = b_by_pr[pr]
        cr = c_by_pr[pr]
        b_routers = br.get("routers") if isinstance(br.get("routers"), dict) else {}
        c_routers = cr.get("routers") if isinstance(cr.get("routers"), dict) else {}
        common_routers = sorted(
            set(b_routers.keys()) & set(c_routers.keys()), key=lambda s: str(s).lower()
        )

        def policy_status(row: dict[str, Any]) -> str | None:
            truth = row.get("truth") if isinstance(row.get("truth"), dict) else {}
            policies = (
                truth.get("policies") if isinstance(truth.get("policies"), dict) else {}
            )
            if policy_id is None:
                return None
            entry = policies.get(policy_id)
            if not isinstance(entry, dict):
                return None
            status = entry.get("status")
            return str(status) if isinstance(status, str) else None

        if policy_id is not None:
            if policy_status(br) != "observed" or policy_status(cr) != "observed":
                continue

        for rid in common_routers:
            bp = b_routers.get(rid) if isinstance(b_routers.get(rid), dict) else {}
            cp = c_routers.get(rid) if isinstance(c_routers.get(rid), dict) else {}

            def metrics_by_policy(payload: dict[str, Any]) -> dict[str, Any]:
                by_policy = payload.get("routing_agreement_by_policy")
                if (
                    isinstance(by_policy, dict)
                    and policy_id is not None
                    and isinstance(by_policy.get(policy_id), dict)
                ):
                    return by_policy.get(policy_id) or {}
                ra = payload.get("routing_agreement")
                return ra if isinstance(ra, dict) else {}

            bm = metrics_by_policy(bp)
            cm = metrics_by_policy(cp)

            dmrr = _delta_number(bm.get("mrr"), cm.get("mrr"))
            if dmrr is None or dmrr >= 0.0:
                continue
            out.append(
                {
                    "pr_number": int(pr),
                    "router_id": str(rid),
                    "policy_id": policy_id,
                    "baseline": {
                        "mrr": bm.get("mrr"),
                        "hit_at_1": bm.get("hit_at_1"),
                    },
                    "candidate": {
                        "mrr": cm.get("mrr"),
                        "hit_at_1": cm.get("hit_at_1"),
                    },
                    "delta": {
                        "mrr": dmrr,
                        "hit_at_1": _delta_number(
                            bm.get("hit_at_1"), cm.get("hit_at_1")
                        ),
                    },
                    "baseline_artifacts": {
                        "run_id": baseline_run_id,
                        "snapshot_json": f"prs/{pr}/snapshot.json",
                        "inputs_json": f"prs/{pr}/inputs.json",
                        "route_json": f"prs/{pr}/routes/{rid}.json",
                    },
                    "candidate_artifacts": {
                        "run_id": candidate_run_id,
                        "snapshot_json": f"prs/{pr}/snapshot.json",
                        "inputs_json": f"prs/{pr}/inputs.json",
                        "route_json": f"prs/{pr}/routes/{rid}.json",
                    },
                }
            )

    out.sort(
        key=lambda r: (
            float((r.get("delta") or {}).get("mrr") or 0.0),
            int(r.get("pr_number") or 0),
            str(r.get("router_id") or "").lower(),
        )
    )
    return out[: max(0, int(limit))]


def _gate_deltas(
    *, baseline_summary: dict[str, Any], candidate_summary: dict[str, Any]
) -> dict[str, Any]:
    b_counts = _truth_coverage_counts(baseline_summary)
    c_counts = _truth_coverage_counts(candidate_summary)
    all_keys = sorted(
        set(b_counts.keys()) | set(c_counts.keys()), key=lambda s: s.lower()
    )
    truth_counts = {
        k: {
            "baseline": int(b_counts.get(k, 0)),
            "candidate": int(c_counts.get(k, 0)),
            "delta": int(c_counts.get(k, 0)) - int(b_counts.get(k, 0)),
        }
        for k in all_keys
    }

    b_q = _get_quality_gate_block(baseline_summary) or {}
    c_q = _get_quality_gate_block(candidate_summary) or {}
    b_all = b_q.get("all_pass") if isinstance(b_q.get("all_pass"), bool) else None
    c_all = c_q.get("all_pass") if isinstance(c_q.get("all_pass"), bool) else None
    b_gates = b_q.get("gates") if isinstance(b_q.get("gates"), dict) else {}
    c_gates = c_q.get("gates") if isinstance(c_q.get("gates"), dict) else {}
    gate_ids = sorted(
        set(b_gates.keys()) | set(c_gates.keys()), key=lambda s: str(s).lower()
    )
    gate_rows: list[dict[str, Any]] = []
    for gid in gate_ids:
        bg = b_gates.get(gid) if isinstance(b_gates.get(gid), dict) else {}
        cg = c_gates.get(gid) if isinstance(c_gates.get(gid), dict) else {}
        gate_rows.append(
            {
                "gate_id": str(gid),
                "baseline_pass": bg.get("pass")
                if isinstance(bg.get("pass"), bool)
                else None,
                "candidate_pass": cg.get("pass")
                if isinstance(cg.get("pass"), bool)
                else None,
                "baseline_value": bg.get("value")
                if isinstance(bg.get("value"), (int, float))
                else None,
                "candidate_value": cg.get("value")
                if isinstance(cg.get("value"), (int, float))
                else None,
                "delta_value": _delta_number(bg.get("value"), cg.get("value")),
            }
        )

    b_p = _get_promotion_block(baseline_summary) or {}
    c_p = _get_promotion_block(candidate_summary) or {}
    b_promote = b_p.get("promote") if isinstance(b_p.get("promote"), bool) else None
    c_promote = c_p.get("promote") if isinstance(c_p.get("promote"), bool) else None

    return {
        "truth_coverage_counts": truth_counts,
        "quality_gates": {
            "baseline_all_pass": b_all,
            "candidate_all_pass": c_all,
            "gate_rows": gate_rows,
        }
        if gate_rows or b_all is not None or c_all is not None
        else None,
        "promotion": {
            "baseline_promote": b_promote,
            "candidate_promote": c_promote,
        }
        if b_promote is not None or c_promote is not None
        else None,
    }


def build_compare_summary(
    *,
    repo: str,
    data_dir: str,
    baseline_run_id: str,
    candidate_run_id: str,
    baseline_run_dir: Path | None = None,
    candidate_run_dir: Path | None = None,
) -> dict[str, Any]:
    b_dir = baseline_run_dir or repo_eval_run_dir(
        repo_full_name=repo, data_dir=data_dir, run_id=baseline_run_id
    )
    c_dir = candidate_run_dir or repo_eval_run_dir(
        repo_full_name=repo, data_dir=data_dir, run_id=candidate_run_id
    )

    # Prefer existing run_summary.json; regenerate if missing.
    b_summary = _read_json(b_dir / "run_summary.json")
    if b_summary is None:
        b_summary = build_run_summary(repo=repo, run_id=baseline_run_id, run_dir=b_dir)
        write_run_summary(repo=repo, run_id=baseline_run_id, run_dir=b_dir)
    c_summary = _read_json(c_dir / "run_summary.json")
    if c_summary is None:
        c_summary = build_run_summary(repo=repo, run_id=candidate_run_id, run_dir=c_dir)
        write_run_summary(repo=repo, run_id=candidate_run_id, run_dir=c_dir)

    b_inputs = (
        b_summary.get("inputs") if isinstance(b_summary.get("inputs"), dict) else {}
    )
    c_inputs = (
        c_summary.get("inputs") if isinstance(c_summary.get("inputs"), dict) else {}
    )
    b_cohort = (
        b_inputs.get("cohort_hash")
        if isinstance(b_inputs.get("cohort_hash"), str)
        else None
    )
    c_cohort = (
        c_inputs.get("cohort_hash")
        if isinstance(c_inputs.get("cohort_hash"), str)
        else None
    )

    b_pr_cutoffs_hash = _pr_cutoffs_hash(b_dir)
    c_pr_cutoffs_hash = _pr_cutoffs_hash(c_dir)

    warnings: list[str] = []
    cohort_match: bool | None = None
    if b_cohort is not None and c_cohort is not None:
        cohort_match = b_cohort == c_cohort
        if not cohort_match:
            warnings.append(f"cohort_hash_mismatch {b_cohort} != {c_cohort}")
    elif b_cohort is not None or c_cohort is not None:
        warnings.append("cohort_hash_missing_in_one_run")

    pr_cutoffs_match: bool | None = None
    if b_pr_cutoffs_hash is not None and c_pr_cutoffs_hash is not None:
        pr_cutoffs_match = b_pr_cutoffs_hash == c_pr_cutoffs_hash
        if not pr_cutoffs_match:
            warnings.append("pr_cutoffs_hash_mismatch")

    b_report = _read_json(b_dir / "report.json")
    c_report = _read_json(c_dir / "report.json")
    if b_report is None or c_report is None:
        raise ValueError("missing report.json in baseline or candidate")

    baseline_metrics = _router_metrics(b_summary)
    candidate_metrics = _router_metrics(c_summary)
    ranked_deltas = _ranked_router_deltas(
        baseline=baseline_metrics, candidate=candidate_metrics
    )

    # Slice deltas (policy + denominator slices).
    top_regressed_slices = _slice_deltas(
        baseline_report=b_report, candidate_report=c_report, limit=20
    )

    # Per-PR example regressions.
    b_rows = _read_jsonl_rows(b_dir / "per_pr.jsonl")
    c_rows = _read_jsonl_rows(c_dir / "per_pr.jsonl")
    primary_policy = (
        c_inputs.get("truth_primary_policy")
        if isinstance(c_inputs.get("truth_primary_policy"), str)
        else b_inputs.get("truth_primary_policy")
    )
    policy_id = (
        str(primary_policy).strip()
        if isinstance(primary_policy, str) and str(primary_policy).strip()
        else None
    )
    top_regressed_examples = _top_regressed_examples(
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
        baseline_rows=b_rows,
        candidate_rows=c_rows,
        policy_id=policy_id,
        limit=20,
    )

    gate_deltas = _gate_deltas(baseline_summary=b_summary, candidate_summary=c_summary)

    baseline_run_dir_rel = _rel_under_data_dir(b_dir, data_dir=data_dir)
    candidate_run_dir_rel = _rel_under_data_dir(c_dir, data_dir=data_dir)
    compare_id = _sha256_text(
        _stable_json_compact(
            {
                "repo": repo,
                "baseline": {
                    "run_id": baseline_run_id,
                    "report_sha256": (b_summary.get("hashes") or {}).get(
                        "report_json_sha256"
                    ),
                    "per_pr_sha256": (b_summary.get("hashes") or {}).get(
                        "per_pr_jsonl_sha256"
                    ),
                },
                "candidate": {
                    "run_id": candidate_run_id,
                    "report_sha256": (c_summary.get("hashes") or {}).get(
                        "report_json_sha256"
                    ),
                    "per_pr_sha256": (c_summary.get("hashes") or {}).get(
                        "per_pr_jsonl_sha256"
                    ),
                },
            }
        )
    )

    payload: dict[str, Any] = {
        "schema_version": 1,
        "kind": "compare_summary",
        "generated_at": _now_iso_utc(),
        "compare_id": compare_id,
        "repo": repo,
        "baseline": {
            "run_id": baseline_run_id,
            "run_dir": baseline_run_dir_rel,
            "cohort_hash": b_cohort,
            "pr_cutoffs_hash": b_pr_cutoffs_hash,
            "watermark": b_summary.get("watermark")
            if isinstance(b_summary.get("watermark"), dict)
            else {},
            "artifacts": {
                "run_summary_json": "run_summary.json",
                "manifest_json": "manifest.json",
                "report_json": "report.json",
                "per_pr_jsonl": "per_pr.jsonl",
            },
        },
        "candidate": {
            "run_id": candidate_run_id,
            "run_dir": candidate_run_dir_rel,
            "cohort_hash": c_cohort,
            "pr_cutoffs_hash": c_pr_cutoffs_hash,
            "watermark": c_summary.get("watermark")
            if isinstance(c_summary.get("watermark"), dict)
            else {},
            "artifacts": {
                "run_summary_json": "run_summary.json",
                "manifest_json": "manifest.json",
                "report_json": "report.json",
                "per_pr_jsonl": "per_pr.jsonl",
                "experiment_manifest_json": "experiment_manifest.json",
            },
        },
        "compatibility": {
            "warnings": sorted(set(warnings), key=lambda s: s.lower()),
            "cohort_hash_match": cohort_match,
            "pr_cutoffs_match": pr_cutoffs_match,
        },
        "ranked_deltas": ranked_deltas,
        "top_regressed_slices": top_regressed_slices,
        "top_regressed_examples": top_regressed_examples,
        "gate_deltas": gate_deltas,
        "drill": {
            "baseline_run_dir": baseline_run_dir_rel,
            "candidate_run_dir": candidate_run_dir_rel,
            "baseline_run_summary": f"{baseline_run_dir_rel}/run_summary.json",
            "candidate_run_summary": f"{candidate_run_dir_rel}/run_summary.json",
        },
    }
    return payload


def write_compare_summary(
    *,
    repo: str,
    data_dir: str,
    baseline_run_id: str,
    candidate_run_id: str,
    out_dir: Path | None = None,
) -> Path:
    base = repo_eval_dir(repo_full_name=repo, data_dir=data_dir)
    compare_dir = out_dir
    if compare_dir is None:
        compare_dir = base / "_compare" / f"{baseline_run_id}__vs__{candidate_run_id}"
    compare_dir.mkdir(parents=True, exist_ok=True)

    payload = build_compare_summary(
        repo=repo,
        data_dir=data_dir,
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
    )
    out_path = compare_dir / "compare_summary.json"
    out_path.write_text(json_dumps(payload), encoding="utf-8")
    return out_path


__all__ = ["build_compare_summary", "write_compare_summary"]
