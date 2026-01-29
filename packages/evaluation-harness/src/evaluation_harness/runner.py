from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

from repo_routing.artifacts.models import RouteArtifact
from repo_routing.artifacts.writer import (
    ArtifactWriter,
    build_pr_snapshot_artifact,
    build_route_result,
)

from .config import EvalRunConfig
from .cutoff import cutoff_for_pr
from .db import RepoDb
from .manifest import build_manifest
from .metrics.gates import GateCorrelation, per_pr_gate_metrics
from .metrics.queue import QueueMetricsAggregator, per_pr_queue_metrics
from .metrics.routing_agreement import RoutingAgreement, per_pr_metrics
from .models import TruthLabel
from .paths import repo_eval_run_dir
from .reporting import render_report_md
from .reporting.models import EvalReport
from .store.filesystem import FilesystemStore
from .truth import behavior_truth_first_eligible_review


@dataclass(frozen=True)
class RunResult:
    run_dir: Path


def run_streaming_eval(
    *,
    cfg: EvalRunConfig,
    pr_numbers: list[int],
    baselines: list[str] | None = None,
) -> RunResult:
    """Run a leakage-safe streaming evaluation.

    This v0 runner uses only offline DB state and enforces that router inputs
    are computed as-of the per-PR cutoff.
    """

    baselines = baselines or ["mentions", "popularity", "codeowners"]
    if not baselines:
        raise ValueError("at least one baseline is required")

    def pkg_version(name: str) -> str | None:
        try:
            return metadata.version(name)
        except Exception:
            return None

    package_versions = {
        "evaluation-harness": pkg_version("evaluation-harness"),
        "repo-routing": pkg_version("repo-routing"),
    }

    generated_at = datetime.now(timezone.utc)
    run_dir = repo_eval_run_dir(
        repo_full_name=cfg.repo, data_dir=cfg.data_dir, run_id=cfg.run_id
    )
    store = FilesystemStore(base_dir=run_dir)

    db = RepoDb(repo=cfg.repo, data_dir=cfg.data_dir)
    conn = db.connect()
    try:
        db_max_event_occurred_at = db.max_event_occurred_at(conn)
        db_max_watermark_updated_at = db.max_watermark_updated_at(conn)
    finally:
        conn.close()

    # Streaming order: cutoff asc, then pr number.
    cutoffs = {
        n: cutoff_for_pr(
            repo=cfg.repo,
            pr_number=n,
            data_dir=cfg.data_dir,
            policy=cfg.defaults.cutoff_policy,
        )
        for n in pr_numbers
    }
    ordered = sorted(pr_numbers, key=lambda n: (cutoffs[n], n))

    routing_writer = ArtifactWriter(
        repo=cfg.repo, data_dir=cfg.data_dir, run_id=cfg.run_id
    )

    routing_rows_by_baseline: dict[str, list[object]] = {b: [] for b in baselines}
    queue_rows_by_baseline: dict[str, list[object]] = {b: [] for b in baselines}
    gate_rows: list[object] = []

    for pr_number in ordered:
        cutoff = cutoffs[pr_number]

        snap = build_pr_snapshot_artifact(
            repo=cfg.repo, pr_number=pr_number, as_of=cutoff, data_dir=cfg.data_dir
        )
        routing_writer.write_pr_snapshot(snap)

        truth_login = behavior_truth_first_eligible_review(
            repo=cfg.repo,
            pr_number=pr_number,
            cutoff=cutoff,
            data_dir=cfg.data_dir,
            exclude_author=cfg.defaults.exclude_author,
            exclude_bots=cfg.defaults.exclude_bots,
        )
        truth_targets = [] if truth_login is None else [truth_login]

        gate_metrics = per_pr_gate_metrics(
            repo=cfg.repo, pr_number=pr_number, cutoff=cutoff, data_dir=cfg.data_dir
        )

        per_baseline: dict[str, object] = {}
        for baseline in baselines:
            result = build_route_result(
                baseline=baseline,
                repo=cfg.repo,
                pr_number=pr_number,
                as_of=cutoff,
                data_dir=cfg.data_dir,
                top_k=cfg.defaults.top_k,
            )
            routing_writer.write_route_result(
                RouteArtifact(baseline=baseline, result=result)
            )

            pr_metrics = per_pr_metrics(
                result=result,
                truth=TruthLabel(
                    repo=cfg.repo,
                    pr_number=pr_number,
                    cutoff=cutoff,
                    targets=truth_targets,
                ),
            )
            queue_metrics = per_pr_queue_metrics(
                result=result,
                baseline=baseline,
                cutoff=cutoff,
                data_dir=cfg.data_dir,
                include_ttfc=False,
            )

            routing_rows_by_baseline[baseline].append(pr_metrics)
            queue_rows_by_baseline[baseline].append(queue_metrics)
            per_baseline[baseline] = {
                "route_result": result.model_dump(mode="json"),
                "routing_agreement": pr_metrics.model_dump(mode="json"),
                "queue": queue_metrics.model_dump(mode="json"),
            }

        row: dict[str, object] = {
            "repo": cfg.repo,
            "run_id": cfg.run_id,
            "pr_number": pr_number,
            "cutoff": cutoff.isoformat(),
            "truth_behavior": truth_targets,
            "gates": gate_metrics.model_dump(mode="json"),
            "baselines": per_baseline,
        }
        store.append_jsonl("per_pr.jsonl", row)
        gate_rows.append(gate_metrics)

    routing_summaries = {
        b: RoutingAgreement(repo=cfg.repo, run_id=cfg.run_id).aggregate(rows)  # type: ignore[arg-type]
        for b, rows in routing_rows_by_baseline.items()
    }
    gates_summary = GateCorrelation(repo=cfg.repo, run_id=cfg.run_id).aggregate(
        gate_rows  # type: ignore[arg-type]
    )
    queue_summaries = {
        b: QueueMetricsAggregator(
            repo=cfg.repo, run_id=cfg.run_id, baseline=b
        ).aggregate(
            rows  # type: ignore[arg-type]
        )
        for b, rows in queue_rows_by_baseline.items()
    }

    notes: list[str] = []
    if db_max_event_occurred_at is not None:
        bad = [n for n in ordered if cutoffs[n] > db_max_event_occurred_at]
        if bad:
            notes.append(
                f"db_max_event_occurred_at={db_max_event_occurred_at.isoformat()} is before cutoffs for PRs: {bad}"
            )

    report = EvalReport(
        repo=cfg.repo,
        run_id=cfg.run_id,
        generated_at=generated_at,
        db_max_event_occurred_at=db_max_event_occurred_at,
        db_max_watermark_updated_at=db_max_watermark_updated_at,
        package_versions=package_versions,
        baselines=list(baselines),
        routing_agreement=routing_summaries,  # type: ignore[arg-type]
        gates=gates_summary,
        queue=queue_summaries,  # type: ignore[arg-type]
        notes=notes,
    )
    store.write_json("report.json", report.model_dump(mode="json"))

    store.write_text(
        "report.md",
        render_report_md(
            repo=cfg.repo,
            run_id=cfg.run_id,
            generated_at=generated_at,
            db_max_event_occurred_at=db_max_event_occurred_at,
            db_max_watermark_updated_at=db_max_watermark_updated_at,
            package_versions=package_versions,
            routing=routing_summaries,  # type: ignore[arg-type]
            gates=gates_summary,
            queue=queue_summaries,  # type: ignore[arg-type]
            notes=notes,
        ),
    )

    manifest = build_manifest(
        cfg=cfg,
        pr_numbers=ordered,
        generated_at=generated_at,
        db_max_event_occurred_at=db_max_event_occurred_at,
        db_max_watermark_updated_at=db_max_watermark_updated_at,
        package_versions=package_versions,
        baselines=list(baselines),
    )
    store.write_json("manifest.json", manifest.model_dump(mode="json"))

    return RunResult(run_dir=run_dir)
