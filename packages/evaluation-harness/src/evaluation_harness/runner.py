from __future__ import annotations

import inspect
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
from repo_routing.inputs.models import PRInputBundle
from repo_routing.predictor.pipeline import PipelinePredictor
from repo_routing.repo_profile.builder import build_repo_profile
from repo_routing.repo_profile.storage import DEFAULT_PINNED_ARTIFACT_PATHS
from repo_routing.registry import RouterSpec, load_router, router_id_for_spec, router_manifest_entry
from repo_routing.time import require_dt_utc

from .config import EvalRunConfig
from .cutoff import cutoff_for_pr
from .db import RepoDb
from .manifest import build_manifest
from .metrics.gates import GateCorrelation, per_pr_gate_metrics
from .metrics.queue import QueueMetricsAggregator, per_pr_queue_metrics
from .metrics.routing_agreement import RoutingAgreement, per_pr_metrics
from .models import TruthLabel, TruthStatus
from .paths import repo_eval_run_dir
from .reporting import render_report_md
from .reporting.models import EvalReport
from .store.filesystem import FilesystemStore
from .truth import behavior_truth_with_diagnostics


@dataclass(frozen=True)
class RunResult:
    run_dir: Path


@dataclass(frozen=True)
class RepoProfileRunSettings:
    strict: bool = True
    artifact_paths: tuple[str, ...] = DEFAULT_PINNED_ARTIFACT_PATHS
    critical_artifact_paths: tuple[str, ...] = ()


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


def _build_repo_profile_for_pr(
    *,
    cfg: EvalRunConfig,
    pr_number: int,
    cutoff: datetime,
    base_sha: str | None,
    routing_writer: ArtifactWriter,
    settings: RepoProfileRunSettings,
) -> dict[str, object]:
    if base_sha is None:
        message = (
            f"repo profile missing base_sha for {cfg.repo}#{pr_number}; "
            "cannot anchor pinned artifacts"
        )
        if settings.strict:
            raise RuntimeError(message)
        return {
            "status": "skipped_missing_base_sha",
            "profile_path": None,
            "qa_path": None,
            "coverage": {
                "artifact_count": 0,
                "codeowners_present": False,
                "critical_artifacts": list(settings.critical_artifact_paths),
                "present_critical_artifacts": [],
                "missing_critical_artifacts": list(settings.critical_artifact_paths),
            },
            "warnings": [message],
            "qa": {
                "status": "skipped_missing_base_sha",
                "warnings": [message],
            },
        }

    built = build_repo_profile(
        repo=cfg.repo,
        pr_number=pr_number,
        cutoff=cutoff,
        base_sha=base_sha,
        data_dir=cfg.data_dir,
        artifact_paths=settings.artifact_paths,
        critical_artifact_paths=settings.critical_artifact_paths,
    )
    profile_path = routing_writer.write_repo_profile(
        pr_number=pr_number, profile=built.profile
    )
    qa_path = routing_writer.write_repo_profile_qa(
        pr_number=pr_number, qa_report=built.qa_report
    )

    coverage = built.qa_report.coverage.model_dump(mode="json")
    warnings = list(built.qa_report.warnings)
    strict_failures: list[str] = []
    if not bool(coverage.get("codeowners_present")):
        strict_failures.append("CODEOWNERS not found in pinned artifacts")
    missing_critical = coverage.get("missing_critical_artifacts") or []
    if missing_critical:
        strict_failures.append(
            "missing critical artifacts: " + ", ".join(sorted(map(str, missing_critical)))
        )
    if strict_failures and settings.strict:
        raise RuntimeError(
            f"repo profile strict failure for {cfg.repo}#{pr_number}: "
            + "; ".join(strict_failures)
        )

    return {
        "status": "ok" if not strict_failures else "degraded",
        "profile_path": str(profile_path),
        "qa_path": str(qa_path),
        "coverage": coverage,
        "warnings": warnings,
        "qa": built.qa_report.model_dump(mode="json"),
    }


def _normalize_pr_cutoffs(
    *,
    cfg: EvalRunConfig,
    pr_numbers: list[int],
    pr_cutoffs: dict[int | str, datetime] | None,
) -> tuple[dict[int, datetime], str]:
    if pr_cutoffs is None:
        computed = {
            n: cutoff_for_pr(
                repo=cfg.repo,
                pr_number=n,
                data_dir=cfg.data_dir,
                policy=cfg.defaults.cutoff_policy,
            )
            for n in pr_numbers
        }
        return computed, "policy"

    normalized: dict[int, datetime] = {}
    missing: list[int] = []
    for pr_number in pr_numbers:
        raw = pr_cutoffs.get(pr_number)
        if raw is None:
            raw = pr_cutoffs.get(str(pr_number))
        if raw is None:
            missing.append(pr_number)
            continue
        normalized[pr_number] = require_dt_utc(
            raw,
            name=f"pr_cutoffs[{pr_number}]",
        )

    if missing:
        raise ValueError(
            "pr_cutoffs missing entries for PR(s): " + ", ".join(str(n) for n in missing)
        )

    return normalized, "provided"


def _router_accepts_input_bundle(router: object) -> bool:
    route_fn = getattr(router, "route", None)
    if route_fn is None:
        return False
    try:
        sig = inspect.signature(route_fn)
    except (TypeError, ValueError):
        return False

    if "input_bundle" in sig.parameters:
        return True
    return any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )


def _route_router(
    *,
    router: object,
    repo: str,
    pr_number: int,
    cutoff: datetime,
    data_dir: str,
    top_k: int,
    input_bundle: PRInputBundle,
):
    kwargs: dict[str, object] = {
        "repo": repo,
        "pr_number": pr_number,
        "as_of": cutoff,
        "data_dir": data_dir,
        "top_k": top_k,
    }
    if _router_accepts_input_bundle(router):
        kwargs["input_bundle"] = input_bundle
    return router.route(**kwargs)  # type: ignore[call-arg, attr-defined]


def run_streaming_eval(
    *,
    cfg: EvalRunConfig,
    pr_numbers: list[int],
    baselines: list[str] | None = None,
    router_specs: list[RouterSpec] | None = None,
    router_config_path: str | Path | None = None,
    repo_profile_settings: RepoProfileRunSettings | None = None,
    pr_cutoffs: dict[int | str, datetime] | None = None,
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

    cutoffs, cutoff_source = _normalize_pr_cutoffs(
        cfg=cfg,
        pr_numbers=pr_numbers,
        pr_cutoffs=pr_cutoffs,
    )
    ordered = sorted(pr_numbers, key=lambda n: (cutoffs[n], n))

    stale_cutoff_note: str | None = None
    if db_max_event_occurred_at is not None:
        stale_cutoff_prs = [n for n in ordered if cutoffs[n] > db_max_event_occurred_at]
        if stale_cutoff_prs:
            stale_cutoff_note = (
                f"db_max_event_occurred_at={db_max_event_occurred_at.isoformat()} "
                f"is before cutoffs for PRs: {stale_cutoff_prs}"
            )
            if cfg.defaults.strict_streaming_eval:
                raise RuntimeError(
                    "strict_streaming_eval violation: "
                    f"{stale_cutoff_note}. "
                    "Refresh ingestion data or disable strict_streaming_eval explicitly."
                )

    routing_writer = ArtifactWriter(
        repo=cfg.repo, data_dir=cfg.data_dir, run_id=cfg.run_id
    )

    routing_rows_by_router: dict[str, list[object]] = {rid: [] for rid in router_ids}
    routing_rows_known_by_router: dict[str, list[object]] = {rid: [] for rid in router_ids}
    queue_rows_by_router: dict[str, list[object]] = {rid: [] for rid in router_ids}
    gate_rows: list[object] = []
    router_feature_meta: dict[str, dict[str, object]] = {}
    truth_window = cfg.defaults.resolved_truth_window()
    truth_primary_policy = cfg.defaults.resolved_truth_primary_policy()
    truth_status_counts: dict[str, int] = {
        TruthStatus.observed.value: 0,
        TruthStatus.no_post_cutoff_response.value: 0,
        TruthStatus.unknown_due_to_ingestion_gap.value: 0,
        TruthStatus.policy_unavailable.value: 0,
    }

    for pr_number in ordered:
        cutoff = cutoffs[pr_number]

        snap = build_pr_snapshot_artifact(
            repo=cfg.repo, pr_number=pr_number, as_of=cutoff, data_dir=cfg.data_dir
        )
        routing_writer.write_pr_snapshot(snap)

        repo_profile_row: dict[str, object] | None = None
        if repo_profile_settings is not None:
            repo_profile_row = _build_repo_profile_for_pr(
                cfg=cfg,
                pr_number=pr_number,
                cutoff=cutoff,
                base_sha=snap.base_sha,
                routing_writer=routing_writer,
                settings=repo_profile_settings,
            )

        inputs = build_pr_inputs_artifact(
            repo=cfg.repo,
            pr_number=pr_number,
            as_of=cutoff,
            data_dir=cfg.data_dir,
        )
        if repo_profile_row is not None:
            inputs = inputs.model_copy(
                update={
                    "repo_profile_path": repo_profile_row.get("profile_path"),
                    "repo_profile_qa": repo_profile_row.get("qa") or {},
                }
            )
        routing_writer.write_pr_inputs(inputs)

        truth_diag = behavior_truth_with_diagnostics(
            repo=cfg.repo,
            pr_number=pr_number,
            cutoff=cutoff,
            data_dir=cfg.data_dir,
            exclude_author=cfg.defaults.exclude_author,
            exclude_bots=cfg.defaults.exclude_bots,
            window=truth_window,
            include_review_comments=cfg.defaults.truth_include_review_comments,
            policy_id=truth_primary_policy,
        )
        truth_targets = [] if truth_diag.selected_login is None else [truth_diag.selected_login]
        truth_status_counts[truth_diag.status.value] = (
            truth_status_counts.get(truth_diag.status.value, 0) + 1
        )

        gate_metrics = per_pr_gate_metrics(
            repo=cfg.repo, pr_number=pr_number, cutoff=cutoff, data_dir=cfg.data_dir
        )

        per_router: dict[str, object] = {}
        for spec in specs:
            router_id = router_id_for_spec(spec)
            router = routers_by_id[router_id]

            result = _route_router(
                router=router,
                repo=cfg.repo,
                pr_number=pr_number,
                cutoff=cutoff,
                data_dir=cfg.data_dir,
                top_k=cfg.defaults.top_k,
                input_bundle=inputs,
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
            if truth_diag.status != TruthStatus.unknown_due_to_ingestion_gap:
                routing_rows_known_by_router[router_id].append(pr_metrics)
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
            "truth_status": truth_diag.status.value,
            "truth_diagnostics": truth_diag.model_dump(mode="json"),
            "gates": gate_metrics.model_dump(mode="json"),
            "routers": per_router,
            "baselines": per_router,
        }
        if repo_profile_row is not None:
            row["repo_profile"] = repo_profile_row
        store.append_jsonl("per_pr.jsonl", row)
        gate_rows.append(gate_metrics)

    routing_summaries = {
        rid: RoutingAgreement(repo=cfg.repo, run_id=cfg.run_id).aggregate(rows)  # type: ignore[arg-type]
        for rid, rows in routing_rows_by_router.items()
    }
    routing_summaries_known = {
        rid: RoutingAgreement(repo=cfg.repo, run_id=cfg.run_id).aggregate(rows)  # type: ignore[arg-type]
        for rid, rows in routing_rows_known_by_router.items()
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
    if stale_cutoff_note is not None:
        notes.append(stale_cutoff_note)

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
        extra={
            "truth_coverage_counts": truth_status_counts,
            "routing_agreement_known_truth": {
                rid: summary.model_dump(mode="json")
                for rid, summary in routing_summaries_known.items()
            },
        },
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
            truth_coverage_counts=truth_status_counts,
            notes=notes,
        ),
    )

    truth_manifest = {
        "policies": list(cfg.defaults.resolved_truth_policy_ids()),
        "primary": truth_primary_policy,
        "effective_window_seconds": int(truth_window.total_seconds()),
        "include_review_comments": bool(cfg.defaults.truth_include_review_comments),
        "policy_hashes": {},
    }

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
        cutoff_source=cutoff_source,
        pr_cutoffs={str(n): cutoffs[n].isoformat() for n in ordered},
        truth=truth_manifest,
    )
    store.write_json("manifest.json", manifest.model_dump(mode="json"))

    return RunResult(run_dir=run_dir)
