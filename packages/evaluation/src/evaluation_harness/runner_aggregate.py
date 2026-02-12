from __future__ import annotations

from .metrics.gates import GateCorrelation
from .metrics.queue import QueueMetricsAggregator
from .metrics.routing_agreement import RoutingAgreement
from .models import TruthStatus
from .reporting.models import EvalReport
from .runner_models import AggregatedEvalStage, PerPrEvalStage, PreparedEvalStage


def aggregate_eval_stage(
    *,
    prepared: PreparedEvalStage,
    per_pr: PerPrEvalStage,
) -> AggregatedEvalStage:
    routing_summaries = {
        rid: RoutingAgreement(repo=prepared.cfg.repo, run_id=prepared.cfg.run_id).aggregate(rows)  # type: ignore[arg-type]
        for rid, rows in per_pr.routing_rows_by_router.items()
    }
    routing_summaries_known = {
        rid: RoutingAgreement(repo=prepared.cfg.repo, run_id=prepared.cfg.run_id).aggregate(rows)  # type: ignore[arg-type]
        for rid, rows in per_pr.routing_rows_known_by_router.items()
    }
    routing_summaries_by_policy = {
        policy_id: {
            rid: RoutingAgreement(repo=prepared.cfg.repo, run_id=prepared.cfg.run_id).aggregate(
                [m for m, _, _ in rows]  # type: ignore[arg-type]
            )
            for rid, rows in by_router.items()
        }
        for policy_id, by_router in per_pr.routing_rows_by_policy_router.items()
    }
    routing_denominators_by_policy: dict[str, dict[str, dict[str, int]]] = {}
    routing_slices_by_policy: dict[str, dict[str, dict[str, dict[str, object]]]] = {}
    for policy_id, by_router in per_pr.routing_rows_by_policy_router.items():
        routing_denominators_by_policy[policy_id] = {}
        routing_slices_by_policy[policy_id] = {}
        for rid, rows in by_router.items():
            all_rows = [m for m, _, _ in rows]
            observed_rows = [m for m, d, _ in rows if d.status == TruthStatus.observed]
            nonempty_rows = [m for m, _, nonempty in rows if nonempty]
            observed_nonempty_rows = [
                m for m, d, nonempty in rows if d.status == TruthStatus.observed and nonempty
            ]
            known_rows = [
                m
                for m, d, _ in rows
                if d.status
                not in {
                    TruthStatus.unknown_due_to_ingestion_gap,
                    TruthStatus.policy_unavailable,
                }
            ]

            routing_denominators_by_policy[policy_id][rid] = {
                "all": len(all_rows),
                "observed": len(observed_rows),
                "router_nonempty": len(nonempty_rows),
                "observed_and_router_nonempty": len(observed_nonempty_rows),
                "known_truth": len(known_rows),
            }
            routing_slices_by_policy[policy_id][rid] = {
                "all": RoutingAgreement(repo=prepared.cfg.repo, run_id=prepared.cfg.run_id)
                .aggregate(all_rows)
                .model_dump(mode="json"),
                "known_truth": RoutingAgreement(
                    repo=prepared.cfg.repo, run_id=prepared.cfg.run_id
                )
                .aggregate(known_rows)
                .model_dump(mode="json"),
                "observed": RoutingAgreement(
                    repo=prepared.cfg.repo, run_id=prepared.cfg.run_id
                )
                .aggregate(observed_rows)
                .model_dump(mode="json"),
                "router_nonempty": RoutingAgreement(
                    repo=prepared.cfg.repo, run_id=prepared.cfg.run_id
                )
                .aggregate(nonempty_rows)
                .model_dump(mode="json"),
                "observed_and_router_nonempty": RoutingAgreement(
                    repo=prepared.cfg.repo, run_id=prepared.cfg.run_id
                )
                .aggregate(observed_nonempty_rows)
                .model_dump(mode="json"),
            }

    gates_summary = GateCorrelation(repo=prepared.cfg.repo, run_id=prepared.cfg.run_id).aggregate(
        per_pr.gate_rows  # type: ignore[arg-type]
    )
    queue_summaries = {
        rid: QueueMetricsAggregator(
            repo=prepared.cfg.repo, run_id=prepared.cfg.run_id, baseline=rid
        ).aggregate(
            rows  # type: ignore[arg-type]
        )
        for rid, rows in per_pr.queue_rows_by_router.items()
    }

    llm_telemetry: dict[str, object] = {"routers": {}, "total_cost_usd": 0.0}
    total_cost = 0.0
    for rid, meta in per_pr.router_feature_meta.items():
        prov = meta.get("llm_provenance")
        if not isinstance(prov, dict):
            continue
        latency = prov.get("latency_ms")
        cost = prov.get("cost_usd")
        if isinstance(cost, (int, float)):
            total_cost += float(cost)
        llm_telemetry["routers"][rid] = {
            "mode": prov.get("mode"),
            "model": prov.get("model"),
            "latency_ms": latency,
            "cost_usd": cost,
        }
    llm_telemetry["total_cost_usd"] = total_cost

    notes: list[str] = []
    if prepared.stale_cutoff_note is not None:
        notes.append(prepared.stale_cutoff_note)

    report = EvalReport(
        repo=prepared.cfg.repo,
        run_id=prepared.cfg.run_id,
        generated_at=prepared.generated_at,
        db_max_event_occurred_at=prepared.db_max_event_occurred_at,
        db_max_watermark_updated_at=prepared.db_max_watermark_updated_at,
        package_versions=prepared.package_versions,
        routers=list(per_pr.routing_rows_by_router),
        baselines=list(per_pr.routing_rows_by_router),
        routing_agreement=routing_summaries,  # type: ignore[arg-type]
        gates=gates_summary,
        queue=queue_summaries,  # type: ignore[arg-type]
        notes=notes,
        extra={
            "truth_primary_policy": prepared.truth_primary_policy,
            "truth_policies": list(prepared.truth_policies),
            "truth_coverage_counts": per_pr.truth_status_counts,
            "truth_coverage_counts_by_policy": per_pr.truth_status_counts_by_policy,
            "routing_agreement_known_truth": {
                rid: summary.model_dump(mode="json")
                for rid, summary in routing_summaries_known.items()
            },
            "routing_agreement_by_policy": {
                policy_id: {
                    rid: summary.model_dump(mode="json")
                    for rid, summary in by_router.items()
                }
                for policy_id, by_router in routing_summaries_by_policy.items()
            },
            "routing_agreement_slices_by_policy": routing_slices_by_policy,
            "routing_denominators_by_policy": routing_denominators_by_policy,
            "llm_telemetry": llm_telemetry,
        },
    )

    truth_manifest = {
        "policies": list(prepared.truth_policies),
        "primary": prepared.truth_primary_policy,
        "effective_window_seconds": prepared.truth_window_seconds,
        "include_review_comments": bool(prepared.cfg.defaults.truth_include_review_comments),
        "policy_hashes": {
            pid: prepared.truth_policies[pid].policy_hash
            for pid in prepared.truth_policies
        },
    }

    return AggregatedEvalStage(
        routing_summaries=routing_summaries,
        routing_summaries_known=routing_summaries_known,
        routing_summaries_by_policy=routing_summaries_by_policy,
        routing_denominators_by_policy=routing_denominators_by_policy,
        routing_slices_by_policy=routing_slices_by_policy,
        gates_summary=gates_summary,
        queue_summaries=queue_summaries,
        llm_telemetry=llm_telemetry,
        notes=notes,
        report=report,
        truth_manifest=truth_manifest,
    )
