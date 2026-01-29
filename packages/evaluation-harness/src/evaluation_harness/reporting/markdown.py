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
            for baseline in sorted(routing.keys(), key=lambda s: s.lower()):
                r = routing[baseline]
                out.append(f"- {baseline}.n: {r.n}")
                if r.hit_at_1 is not None:
                    out.append(f"- {baseline}.hit@1: {r.hit_at_1:.4f}")
                if r.hit_at_3 is not None:
                    out.append(f"- {baseline}.hit@3: {r.hit_at_3:.4f}")
                if r.hit_at_5 is not None:
                    out.append(f"- {baseline}.hit@5: {r.hit_at_5:.4f}")
                if r.mrr is not None:
                    out.append(f"- {baseline}.mrr: {r.mrr:.4f}")
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
            for baseline in sorted(queue.keys(), key=lambda s: s.lower()):
                q = queue[baseline]
                out.append(f"- {baseline}.n: {q.n}")
                for risk in sorted(q.by_risk.keys(), key=lambda s: s.lower()):
                    b = q.by_risk[risk]
                    out.append(f"- {baseline}.{risk}.n: {b.n}")
                    if b.ttfr_seconds_mean is not None:
                        out.append(
                            f"- {baseline}.{risk}.ttfr_seconds_mean: {b.ttfr_seconds_mean:.2f}"
                        )
                    if b.ttfc_seconds_mean is not None:
                        out.append(
                            f"- {baseline}.{risk}.ttfc_seconds_mean: {b.ttfc_seconds_mean:.2f}"
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

    if notes:
        out.append("## Notes")
        out.append("")
        for n in notes:
            out.append(f"- {n}")
        out.append("")

    return "\n".join(out)
