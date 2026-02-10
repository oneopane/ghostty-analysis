from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

from repo_routing.artifacts.models import RouteArtifact
from repo_routing.artifacts.writer import (
    ArtifactWriter,
    build_pr_inputs_artifact,
    build_pr_snapshot_artifact,
)
from repo_routing.predictor.pipeline import PipelinePredictor
from repo_routing.registry import RouterSpec, load_router, router_id_for_spec, router_manifest_entry

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


def _normalize_router_specs(
    *,
    baselines: list[str] | None,
    router_specs: list[RouterSpec] | None,
    router_config_path: str | Path | None,
) -> list[RouterSpec]:
    if router_specs:
        specs = [s.model_copy() for s in router_specs]
    else:
        names = baselines or ["mentions", "popularity", "codeowners"]
        specs = [RouterSpec(type="builtin", name=n) for n in names]

    if not specs:
        raise ValueError("at least one router is required")

    if router_config_path is not None:
        for i, spec in enumerate(specs):
            if spec.type == "builtin" and spec.name == "stewards" and not spec.config_path:
                specs[i] = spec.model_copy(update={"config_path": str(router_config_path)})

    for spec in specs:
        if spec.type == "builtin" and spec.name == "stewards" and not spec.config_path:
            raise ValueError("router_config_path is required for stewards")

    return specs


def run_streaming_eval(
    *,
    cfg: EvalRunConfig,
    pr_numbers: list[int],
    baselines: list[str] | None = None,
    router_specs: list[RouterSpec] | None = None,
    router_config_path: str | Path | None = None,
) -> RunResult:
    """Run a leakage-safe streaming evaluation."""

    specs = _normalize_router_specs(
        baselines=baselines,
        router_specs=router_specs,
        router_config_path=router_config_path,
    )
    router_ids = [router_id_for_spec(s) for s in specs]

    routers_by_id = {
        router_id_for_spec(spec): load_router(spec)
        for spec in specs
    }

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

    routing_rows_by_router: dict[str, list[object]] = {rid: [] for rid in router_ids}
    queue_rows_by_router: dict[str, list[object]] = {rid: [] for rid in router_ids}
    gate_rows: list[object] = []
    router_feature_meta: dict[str, dict[str, object]] = {}

    for pr_number in ordered:
        cutoff = cutoffs[pr_number]

        snap = build_pr_snapshot_artifact(
            repo=cfg.repo, pr_number=pr_number, as_of=cutoff, data_dir=cfg.data_dir
        )
        routing_writer.write_pr_snapshot(snap)

        inputs = build_pr_inputs_artifact(
            repo=cfg.repo,
            pr_number=pr_number,
            as_of=cutoff,
            data_dir=cfg.data_dir,
        )
        routing_writer.write_pr_inputs(inputs)

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

        per_router: dict[str, object] = {}
        for spec in specs:
            router_id = router_id_for_spec(spec)
            router = routers_by_id[router_id]

            result = router.route(
                repo=cfg.repo,
                pr_number=pr_number,
                as_of=cutoff,
                data_dir=cfg.data_dir,
                top_k=cfg.defaults.top_k,
            )

            predictor = getattr(router, "predictor", None)
            feature_meta: dict[str, object] = {}
            if isinstance(predictor, PipelinePredictor) and predictor.last_features is not None:
                routing_writer.write_features(
                    pr_number=pr_number,
                    router_id=router_id,
                    features=predictor.last_features,
                )
                raw_meta = predictor.last_features.get("meta")
                if isinstance(raw_meta, dict):
                    for k in ("candidate_gen_version", "task_policy", "feature_registry"):
                        if k in raw_meta:
                            feature_meta[k] = raw_meta[k]
                if "feature_version" in predictor.last_features:
                    feature_meta["feature_version"] = predictor.last_features["feature_version"]
                if router_id not in router_feature_meta and feature_meta:
                    router_feature_meta[router_id] = feature_meta

            routing_writer.write_route_result(
                RouteArtifact(baseline=router_id, result=result, meta=feature_meta)
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
                baseline=router_id,
                cutoff=cutoff,
                data_dir=cfg.data_dir,
                include_ttfc=False,
            )

            routing_rows_by_router[router_id].append(pr_metrics)
            queue_rows_by_router[router_id].append(queue_metrics)
            per_router[router_id] = {
                "route_result": result.model_dump(mode="json"),
                "feature_meta": feature_meta,
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
            "routers": per_router,
            "baselines": per_router,
        }
        store.append_jsonl("per_pr.jsonl", row)
        gate_rows.append(gate_metrics)

    routing_summaries = {
        rid: RoutingAgreement(repo=cfg.repo, run_id=cfg.run_id).aggregate(rows)  # type: ignore[arg-type]
        for rid, rows in routing_rows_by_router.items()
    }
    gates_summary = GateCorrelation(repo=cfg.repo, run_id=cfg.run_id).aggregate(
        gate_rows  # type: ignore[arg-type]
    )
    queue_summaries = {
        rid: QueueMetricsAggregator(
            repo=cfg.repo, run_id=cfg.run_id, baseline=rid
        ).aggregate(
            rows  # type: ignore[arg-type]
        )
        for rid, rows in queue_rows_by_router.items()
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
        routers=list(router_ids),
        baselines=list(router_ids),
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
        baselines=list(router_ids),
        routers=[router_manifest_entry(s) for s in specs],
        router_feature_meta={k: router_feature_meta[k] for k in sorted(router_feature_meta)},
    )
    store.write_json("manifest.json", manifest.model_dump(mode="json"))

    return RunResult(run_dir=run_dir)
