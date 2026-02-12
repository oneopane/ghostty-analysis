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
from .models import PRMetrics, TruthDiagnostics, TruthLabel, TruthStatus
from .paths import repo_eval_run_dir
from .reporting import render_report_md
from .reporting.models import EvalReport
from .store.filesystem import FilesystemStore
from .truth import truth_with_policy
from .truth_policy import ResolvedTruthPolicy, resolve_truth_policies


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
    for router in routers_by_id.values():
        if hasattr(router, "mode") and isinstance(getattr(router, "mode"), str):
            setattr(router, "mode", str(cfg.defaults.llm_mode or "replay").strip().lower())

    def pkg_version(name: str) -> str | None:
        try:
            return metadata.version(name)
        except Exception:
            return None

    package_versions = {
        "evaluation": pkg_version("evaluation"),
        "inference": pkg_version("inference"),
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

    truth_window = cfg.defaults.resolved_truth_window()
    resolved_truth_policies = resolve_truth_policies(
        policy_ids=cfg.defaults.resolved_truth_policy_ids(),
        plugin_import_paths=cfg.defaults.truth_policy_plugins,
        plugin_allowlist_prefixes=cfg.defaults.truth_policy_plugin_allowlist,
    )
    truth_window_seconds = int(truth_window.total_seconds())
    truth_policies = {
        pid: ResolvedTruthPolicy(
            spec=resolved.spec.model_copy(update={"window_seconds": truth_window_seconds}),
            source=resolved.source,
            source_ref=resolved.source_ref,
            policy_hash=resolved.spec.model_copy(
                update={"window_seconds": truth_window_seconds}
            ).stable_hash(),
        )
        for pid, resolved in resolved_truth_policies.items()
    }
    routing_rows_by_router: dict[str, list[object]] = {rid: [] for rid in router_ids}
    routing_rows_known_by_router: dict[str, list[object]] = {rid: [] for rid in router_ids}
    routing_rows_by_policy_router: dict[
        str, dict[str, list[tuple[PRMetrics, TruthDiagnostics, bool]]]
    ] = {
        pid: {rid: [] for rid in router_ids}
        for pid in truth_policies
    }
    queue_rows_by_router: dict[str, list[object]] = {rid: [] for rid in router_ids}
    gate_rows: list[object] = []
    router_feature_meta: dict[str, dict[str, object]] = {}
    truth_primary_policy = cfg.defaults.resolved_truth_primary_policy()
    if truth_primary_policy not in truth_policies:
        raise ValueError(
            f"truth_primary_policy is not active: {truth_primary_policy}; "
            f"active={list(truth_policies)}"
        )
    truth_status_counts: dict[str, int] = {
        TruthStatus.observed.value: 0,
        TruthStatus.no_post_cutoff_response.value: 0,
        TruthStatus.unknown_due_to_ingestion_gap.value: 0,
        TruthStatus.policy_unavailable.value: 0,
    }
    truth_status_counts_by_policy: dict[str, dict[str, int]] = {
        pid: {
            TruthStatus.observed.value: 0,
            TruthStatus.no_post_cutoff_response.value: 0,
            TruthStatus.unknown_due_to_ingestion_gap.value: 0,
            TruthStatus.policy_unavailable.value: 0,
        }
        for pid in truth_policies
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

        truth_diags: dict[str, TruthDiagnostics] = {}
        for policy_id, resolved in truth_policies.items():
            diag = truth_with_policy(
                policy=resolved.spec,
                repo=cfg.repo,
                pr_number=pr_number,
                cutoff=cutoff,
                data_dir=cfg.data_dir,
                exclude_author=cfg.defaults.exclude_author,
                exclude_bots=cfg.defaults.exclude_bots,
            )
            truth_diags[policy_id] = diag
            truth_status_counts_by_policy[policy_id][diag.status.value] = (
                truth_status_counts_by_policy[policy_id].get(diag.status.value, 0) + 1
            )

        truth_diag = truth_diags[truth_primary_policy]
        truth_targets = [] if truth_diag.selected_login is None else [truth_diag.selected_login]
        truth_status_counts[truth_diag.status.value] = truth_status_counts.get(
            truth_diag.status.value, 0
        ) + 1

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

            router_provenance = getattr(router, "provenance", None)
            if isinstance(router_provenance, dict):
                feature_meta["router_provenance"] = router_provenance
                if router_id not in router_feature_meta:
                    router_feature_meta[router_id] = dict(feature_meta)

            llm_steps = getattr(router, "last_llm_steps", None)
            if isinstance(llm_steps, dict):
                for step in sorted(llm_steps.keys(), key=str.lower):
                    payload = llm_steps.get(step)
                    if isinstance(payload, dict):
                        routing_writer.write_llm_step(
                            pr_number=pr_number,
                            router_id=router_id,
                            step=str(step),
                            payload=payload,
                        )
            llm_provenance = getattr(router, "last_provenance", None)
            if isinstance(llm_provenance, dict):
                feature_meta["llm_provenance"] = llm_provenance
            if feature_meta:
                router_feature_meta[router_id] = dict(feature_meta)

            routing_writer.write_route_result(
                RouteArtifact(baseline=router_id, result=result, meta=feature_meta)
            )

            pr_metrics_primary = per_pr_metrics(
                result=result,
                truth=TruthLabel(
                    repo=cfg.repo,
                    pr_number=pr_number,
                    cutoff=cutoff,
                    targets=truth_targets,
                ),
            )
            pr_metrics_by_policy: dict[str, PRMetrics] = {}
            for policy_id, diag in truth_diags.items():
                targets = (
                    [] if diag.selected_login is None else [diag.selected_login]
                )
                pr_metrics_by_policy[policy_id] = per_pr_metrics(
                    result=result,
                    truth=TruthLabel(
                        repo=cfg.repo,
                        pr_number=pr_number,
                        cutoff=cutoff,
                        targets=targets,
                    ),
                )
            queue_metrics = per_pr_queue_metrics(
                result=result,
                baseline=router_id,
                cutoff=cutoff,
                data_dir=cfg.data_dir,
                include_ttfc=False,
            )

            routing_rows_by_router[router_id].append(pr_metrics_primary)
            if truth_diag.status != TruthStatus.unknown_due_to_ingestion_gap:
                routing_rows_known_by_router[router_id].append(pr_metrics_primary)
            for policy_id, diag in truth_diags.items():
                routing_rows_by_policy_router[policy_id][router_id].append(
                    (
                        pr_metrics_by_policy[policy_id],
                        diag,
                        bool(result.candidates),
                    )
                )
            queue_rows_by_router[router_id].append(queue_metrics)
            per_router[router_id] = {
                "route_result": result.model_dump(mode="json"),
                "feature_meta": feature_meta,
                "routing_agreement": pr_metrics_primary.model_dump(mode="json"),
                "routing_agreement_by_policy": {
                    pid: pr_metrics_by_policy[pid].model_dump(mode="json")
                    for pid in truth_policies
                },
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
            "truth": {
                "version": "v1",
                "primary_policy": truth_primary_policy,
                "policies": {
                    pid: {
                        "targets": (
                            []
                            if truth_diags[pid].selected_login is None
                            else [truth_diags[pid].selected_login]
                        ),
                        "status": truth_diags[pid].status.value,
                        "diagnostics": truth_diags[pid].model_dump(mode="json"),
                        "policy_hash": truth_policies[pid].policy_hash,
                        "policy_source": truth_policies[pid].source,
                        "policy_source_ref": truth_policies[pid].source_ref,
                    }
                    for pid in truth_policies
                },
            },
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
    routing_summaries_by_policy = {
        policy_id: {
            rid: RoutingAgreement(repo=cfg.repo, run_id=cfg.run_id).aggregate(
                [m for m, _, _ in rows]  # type: ignore[arg-type]
            )
            for rid, rows in by_router.items()
        }
        for policy_id, by_router in routing_rows_by_policy_router.items()
    }
    routing_denominators_by_policy: dict[str, dict[str, dict[str, int]]] = {}
    routing_slices_by_policy: dict[str, dict[str, dict[str, dict[str, object]]]] = {}
    for policy_id, by_router in routing_rows_by_policy_router.items():
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
                if d.status not in {TruthStatus.unknown_due_to_ingestion_gap, TruthStatus.policy_unavailable}
            ]

            routing_denominators_by_policy[policy_id][rid] = {
                "all": len(all_rows),
                "observed": len(observed_rows),
                "router_nonempty": len(nonempty_rows),
                "observed_and_router_nonempty": len(observed_nonempty_rows),
                "known_truth": len(known_rows),
            }
            routing_slices_by_policy[policy_id][rid] = {
                "all": RoutingAgreement(repo=cfg.repo, run_id=cfg.run_id)
                .aggregate(all_rows)
                .model_dump(mode="json"),
                "known_truth": RoutingAgreement(repo=cfg.repo, run_id=cfg.run_id)
                .aggregate(known_rows)
                .model_dump(mode="json"),
                "observed": RoutingAgreement(repo=cfg.repo, run_id=cfg.run_id)
                .aggregate(observed_rows)
                .model_dump(mode="json"),
                "router_nonempty": RoutingAgreement(repo=cfg.repo, run_id=cfg.run_id)
                .aggregate(nonempty_rows)
                .model_dump(mode="json"),
                "observed_and_router_nonempty": RoutingAgreement(repo=cfg.repo, run_id=cfg.run_id)
                .aggregate(observed_nonempty_rows)
                .model_dump(mode="json"),
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

    llm_telemetry: dict[str, object] = {"routers": {}, "total_cost_usd": 0.0}
    total_cost = 0.0
    for rid, meta in router_feature_meta.items():
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
            "truth_primary_policy": truth_primary_policy,
            "truth_policies": list(truth_policies),
            "truth_coverage_counts": truth_status_counts,
            "truth_coverage_counts_by_policy": truth_status_counts_by_policy,
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
            truth_primary_policy=truth_primary_policy,
            routing_by_policy=routing_summaries_by_policy,  # type: ignore[arg-type]
            routing_slices_by_policy=routing_slices_by_policy,
            routing_denominators_by_policy=routing_denominators_by_policy,
            llm_telemetry=llm_telemetry,
            notes=notes,
        ),
    )

    truth_manifest = {
        "policies": list(truth_policies),
        "primary": truth_primary_policy,
        "effective_window_seconds": int(truth_window.total_seconds()),
        "include_review_comments": bool(cfg.defaults.truth_include_review_comments),
        "policy_hashes": {
            pid: truth_policies[pid].policy_hash for pid in truth_policies
        },
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
