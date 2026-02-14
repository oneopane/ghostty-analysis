from __future__ import annotations

from datetime import datetime

from ..models import (
    GateCorrelationSummary,
    QueueSummary,
    RoutingAgreementSummary,
)


def render_report_md(
    *,
    repo: str,
    run_id: str,
    generated_at: datetime,
    db_max_event_occurred_at: datetime | None = None,
    db_max_watermark_updated_at: datetime | None = None,
    package_versions: dict[str, str | None] | None = None,
    routing: RoutingAgreementSummary | dict[str, RoutingAgreementSummary] | None,
    gates: GateCorrelationSummary | None,
    queue: QueueSummary | dict[str, QueueSummary] | None,
    truth_coverage_counts: dict[str, int] | None = None,
    truth_primary_policy: str | None = None,
    routing_by_policy: dict[str, dict[str, RoutingAgreementSummary]] | None = None,
    routing_slices_by_policy: dict[str, dict[str, dict[str, dict[str, object]]]] | None = None,
    routing_denominators_by_policy: dict[str, dict[str, dict[str, int]]] | None = None,
    llm_telemetry: dict[str, object] | None = None,
    notes: list[str] | None = None,
) -> str:
    out: list[str] = []
    out.append(f"# Evaluation Report")
    out.append("")
    out.append(f"- repo: {repo}")
    out.append(f"- run_id: {run_id}")
    out.append(f"- generated_at: {generated_at.isoformat()}")
    if db_max_event_occurred_at is not None:
        out.append(
            f"- db_max_event_occurred_at: {db_max_event_occurred_at.isoformat()}"
        )
    if db_max_watermark_updated_at is not None:
        out.append(
            f"- db_max_watermark_updated_at: {db_max_watermark_updated_at.isoformat()}"
        )
    if package_versions:
        for k in sorted(package_versions.keys(), key=lambda s: s.lower()):
            out.append(f"- {k}_version: {package_versions[k]}")
    out.append("")

    if routing is not None:
        out.append("## Routing Agreement")
        out.append("")
        if isinstance(routing, dict):
            for router_id in sorted(routing.keys(), key=lambda s: s.lower()):
                r = routing[router_id]
                out.append(f"- {router_id}.n: {r.n}")
                if r.hit_at_1 is not None:
                    out.append(f"- {router_id}.hit@1: {r.hit_at_1:.4f}")
                if r.hit_at_3 is not None:
                    out.append(f"- {router_id}.hit@3: {r.hit_at_3:.4f}")
                if r.hit_at_5 is not None:
                    out.append(f"- {router_id}.hit@5: {r.hit_at_5:.4f}")
                if r.mrr is not None:
                    out.append(f"- {router_id}.mrr: {r.mrr:.4f}")
        else:
            out.append(f"- n: {routing.n}")
            if routing.hit_at_1 is not None:
                out.append(f"- hit@1: {routing.hit_at_1:.4f}")
            if routing.hit_at_3 is not None:
                out.append(f"- hit@3: {routing.hit_at_3:.4f}")
            if routing.hit_at_5 is not None:
                out.append(f"- hit@5: {routing.hit_at_5:.4f}")
            if routing.mrr is not None:
                out.append(f"- mrr: {routing.mrr:.4f}")
        out.append("")

    if gates is not None:
        out.append("## Gate Correlation")
        out.append("")
        out.append(f"- n: {gates.n}")

        fields = [
            ("issue", gates.issue),
            ("ai_disclosure", gates.ai_disclosure),
            ("provenance", gates.provenance),
        ]
        for name, f in fields:
            if f is None:
                continue
            out.append(f"- {name}.n: {f.n}")
            out.append(f"- {name}.missing_n: {f.missing_n}")
            out.append(f"- {name}.present_n: {f.present_n}")
            if f.missing_rate is not None:
                out.append(f"- {name}.missing_rate: {f.missing_rate:.4f}")
            if f.merged_rate_missing is not None:
                out.append(f"- {name}.merged_rate_missing: {f.merged_rate_missing:.4f}")
            if f.merged_rate_present is not None:
                out.append(f"- {name}.merged_rate_present: {f.merged_rate_present:.4f}")
        out.append("")

    if queue is not None:
        out.append("## Queue Metrics")
        out.append("")
        if isinstance(queue, dict):
            for router_id in sorted(queue.keys(), key=lambda s: s.lower()):
                q = queue[router_id]
                out.append(f"- {router_id}.n: {q.n}")
                for risk in sorted(q.by_risk.keys(), key=lambda s: s.lower()):
                    b = q.by_risk[risk]
                    out.append(f"- {router_id}.{risk}.n: {b.n}")
                    if b.ttfr_seconds_mean is not None:
                        out.append(
                            f"- {router_id}.{risk}.ttfr_seconds_mean: {b.ttfr_seconds_mean:.2f}"
                        )
                    if b.ttfc_seconds_mean is not None:
                        out.append(
                            f"- {router_id}.{risk}.ttfc_seconds_mean: {b.ttfc_seconds_mean:.2f}"
                        )
        else:
            out.append(f"- n: {queue.n}")
            for risk in sorted(queue.by_risk.keys(), key=lambda s: s.lower()):
                b = queue.by_risk[risk]
                out.append(f"- {risk}.n: {b.n}")
                if b.ttfr_seconds_mean is not None:
                    out.append(f"- {risk}.ttfr_seconds_mean: {b.ttfr_seconds_mean:.2f}")
                if b.ttfc_seconds_mean is not None:
                    out.append(f"- {risk}.ttfc_seconds_mean: {b.ttfc_seconds_mean:.2f}")
        out.append("")

    if truth_coverage_counts:
        out.append("## Truth Coverage")
        out.append("")
        if truth_primary_policy:
            out.append(f"- primary_policy: {truth_primary_policy}")
        for key in sorted(truth_coverage_counts.keys(), key=lambda s: s.lower()):
            out.append(f"- {key}: {int(truth_coverage_counts[key])}")
        out.append("")

    if routing_by_policy:
        out.append("## Routing By Policy")
        out.append("")
        for policy in sorted(routing_by_policy.keys(), key=lambda s: s.lower()):
            out.append(f"- policy: {policy}")
            by_router = routing_by_policy[policy]
            for router_id in sorted(by_router.keys(), key=lambda s: s.lower()):
                summary = by_router[router_id]
                out.append(f"- {policy}.{router_id}.n: {summary.n}")
                if summary.mrr is not None:
                    out.append(f"- {policy}.{router_id}.mrr: {summary.mrr:.4f}")
        out.append("")

    if routing_denominators_by_policy:
        out.append("## Denominator Slices")
        out.append("")
        for policy in sorted(routing_denominators_by_policy.keys(), key=lambda s: s.lower()):
            out.append(f"- policy: {policy}")
            by_router = routing_denominators_by_policy[policy]
            for router_id in sorted(by_router.keys(), key=lambda s: s.lower()):
                den = by_router[router_id]
                out.append(f"- {policy}.{router_id}.all: {int(den.get('all', 0))}")
                out.append(
                    f"- {policy}.{router_id}.observed_and_router_nonempty: {int(den.get('observed_and_router_nonempty', 0))}"
                )
                if routing_slices_by_policy:
                    router_slices = (
                        routing_slices_by_policy.get(policy, {}).get(router_id, {})
                    )
                    obs_nonempty = router_slices.get("observed_and_router_nonempty", {})
                    if isinstance(obs_nonempty, dict):
                        mrr = obs_nonempty.get("mrr")
                        if isinstance(mrr, (int, float)):
                            out.append(
                                f"- {policy}.{router_id}.observed_and_router_nonempty.mrr: {float(mrr):.4f}"
                            )
        out.append("")

    if llm_telemetry:
        out.append("## LLM Telemetry")
        out.append("")
        total_cost = llm_telemetry.get("total_cost_usd")
        if isinstance(total_cost, (int, float)):
            out.append(f"- total_cost_usd: {float(total_cost):.6f}")
        routers = llm_telemetry.get("routers")
        if isinstance(routers, dict):
            for rid in sorted(routers.keys(), key=lambda s: str(s).lower()):
                payload = routers[rid]
                if not isinstance(payload, dict):
                    continue
                out.append(f"- {rid}.mode: {payload.get('mode')}")
                out.append(f"- {rid}.model: {payload.get('model')}")
                out.append(f"- {rid}.latency_ms: {payload.get('latency_ms')}")
                out.append(f"- {rid}.cost_usd: {payload.get('cost_usd')}")
        out.append("")

    if notes:
        out.append("## Notes")
        out.append("")
        for n in notes:
            out.append(f"- {n}")
        out.append("")

    return "\n".join(out)
