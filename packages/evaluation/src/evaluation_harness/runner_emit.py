from __future__ import annotations

from repo_routing.registry import router_manifest_entry

from .manifest import build_manifest
from .reporting import render_report_md
from .run_summary import write_run_summary
from .runner_models import (
    AggregatedEvalStage,
    PerPrEvalStage,
    PreparedEvalStage,
    RunResult,
)


def emit_eval_stage(
    *,
    prepared: PreparedEvalStage,
    per_pr: PerPrEvalStage,
    aggregated: AggregatedEvalStage,
) -> RunResult:
    prepared.store.write_json("report.json", aggregated.report.model_dump(mode="json"))
    prepared.store.write_text(
        "report.md",
        render_report_md(
            repo=prepared.cfg.repo,
            run_id=prepared.cfg.run_id,
            generated_at=prepared.generated_at,
            db_max_event_occurred_at=prepared.db_max_event_occurred_at,
            db_max_watermark_updated_at=prepared.db_max_watermark_updated_at,
            package_versions=prepared.package_versions,
            routing=aggregated.routing_summaries,  # type: ignore[arg-type]
            gates=aggregated.gates_summary,
            queue=aggregated.queue_summaries,  # type: ignore[arg-type]
            truth_coverage_counts=per_pr.truth_status_counts,
            truth_primary_policy=prepared.truth_primary_policy,
            routing_by_policy=aggregated.routing_summaries_by_policy,  # type: ignore[arg-type]
            routing_slices_by_policy=aggregated.routing_slices_by_policy,
            routing_denominators_by_policy=aggregated.routing_denominators_by_policy,
            llm_telemetry=aggregated.llm_telemetry,
            notes=aggregated.notes,
        ),
    )

    manifest = build_manifest(
        cfg=prepared.cfg,
        pr_numbers=prepared.ordered_pr_numbers,
        generated_at=prepared.generated_at,
        db_max_event_occurred_at=prepared.db_max_event_occurred_at,
        db_max_watermark_updated_at=prepared.db_max_watermark_updated_at,
        package_versions=prepared.package_versions,
        baselines=sorted(per_pr.routing_rows_by_router, key=str.lower),
        routers=[router_manifest_entry(s) for s in prepared.specs],
        router_feature_meta={
            k: per_pr.router_feature_meta[k] for k in sorted(per_pr.router_feature_meta)
        },
        cutoff_source=prepared.cutoff_source,
        pr_cutoffs={
            str(n): prepared.cutoffs[n].isoformat() for n in prepared.ordered_pr_numbers
        },
        truth=aggregated.truth_manifest,
    )
    prepared.store.write_json("manifest.json", manifest.model_dump(mode="json"))

    # run_summary.json is the primary automation entrypoint; derive it from the
    # on-disk artifacts to keep it replayable and stable.
    write_run_summary(
        repo=prepared.cfg.repo, run_id=prepared.cfg.run_id, run_dir=prepared.run_dir
    )
    return RunResult(run_dir=prepared.run_dir)
