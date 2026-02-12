from __future__ import annotations

import inspect
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from repo_routing.artifacts.models import RouteArtifact
from repo_routing.artifacts.writer import (
    ArtifactWriter,
    build_pr_inputs_artifact,
    build_pr_snapshot_artifact,
)
from repo_routing.inputs.models import PRInputBundle
from repo_routing.predictor.pipeline import PipelinePredictor
from repo_routing.repo_profile.builder import build_repo_profile

from .metrics.gates import per_pr_gate_metrics
from .metrics.queue import per_pr_queue_metrics
from .metrics.routing_agreement import per_pr_metrics
from .models import PRMetrics, TruthDiagnostics, TruthLabel, TruthStatus
from .runner_models import PerPrEvalStage, PreparedEvalStage, RepoProfileRunSettings
from .truth import truth_with_policy


def _build_repo_profile_for_pr(
    *,
    prepared: PreparedEvalStage,
    pr_number: int,
    cutoff: datetime,
    base_sha: str | None,
    routing_writer: ArtifactWriter,
    settings: RepoProfileRunSettings,
) -> dict[str, object]:
    if base_sha is None:
        message = (
            f"repo profile missing base_sha for {prepared.cfg.repo}#{pr_number}; "
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
        repo=prepared.cfg.repo,
        pr_number=pr_number,
        cutoff=cutoff,
        base_sha=base_sha,
        data_dir=prepared.cfg.data_dir,
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
            f"repo profile strict failure for {prepared.cfg.repo}#{pr_number}: "
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


def _collect_router_run(
    *,
    prepared: PreparedEvalStage,
    router_id: str,
    pr_number: int,
    cutoff: datetime,
    inputs: PRInputBundle,
):
    router = prepared.routers_by_id[router_id]
    result = _route_router(
        router=router,
        repo=prepared.cfg.repo,
        pr_number=pr_number,
        cutoff=cutoff,
        data_dir=prepared.cfg.data_dir,
        top_k=prepared.cfg.defaults.top_k,
        input_bundle=inputs,
    )
    return router_id, result, router


def _sorted_router_ids(prepared: PreparedEvalStage) -> list[str]:
    return sorted(prepared.router_ids, key=str.lower)


def per_pr_evaluate_stage(
    *,
    prepared: PreparedEvalStage,
    repo_profile_settings: RepoProfileRunSettings | None,
) -> PerPrEvalStage:
    routing_writer = ArtifactWriter(
        repo=prepared.cfg.repo,
        data_dir=prepared.cfg.data_dir,
        run_id=prepared.cfg.run_id,
    )
    ordered_router_ids = _sorted_router_ids(prepared)

    routing_rows_by_router: dict[str, list[object]] = {rid: [] for rid in ordered_router_ids}
    routing_rows_known_by_router: dict[str, list[object]] = {
        rid: [] for rid in ordered_router_ids
    }
    routing_rows_by_policy_router: dict[
        str, dict[str, list[tuple[PRMetrics, TruthDiagnostics, bool]]]
    ] = {
        pid: {rid: [] for rid in ordered_router_ids}
        for pid in prepared.truth_policies
    }
    queue_rows_by_router: dict[str, list[object]] = {rid: [] for rid in ordered_router_ids}
    gate_rows: list[object] = []
    router_feature_meta: dict[str, dict[str, object]] = {}
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
        for pid in prepared.truth_policies
    }

    for pr_number in prepared.ordered_pr_numbers:
        cutoff = prepared.cutoffs[pr_number]

        snap = build_pr_snapshot_artifact(
            repo=prepared.cfg.repo,
            pr_number=pr_number,
            as_of=cutoff,
            data_dir=prepared.cfg.data_dir,
        )
        routing_writer.write_pr_snapshot(snap)

        repo_profile_row: dict[str, object] | None = None
        if repo_profile_settings is not None:
            repo_profile_row = _build_repo_profile_for_pr(
                prepared=prepared,
                pr_number=pr_number,
                cutoff=cutoff,
                base_sha=snap.base_sha,
                routing_writer=routing_writer,
                settings=repo_profile_settings,
            )

        inputs = build_pr_inputs_artifact(
            repo=prepared.cfg.repo,
            pr_number=pr_number,
            as_of=cutoff,
            data_dir=prepared.cfg.data_dir,
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
        for policy_id, resolved in prepared.truth_policies.items():
            diag = truth_with_policy(
                policy=resolved.spec,
                repo=prepared.cfg.repo,
                pr_number=pr_number,
                cutoff=cutoff,
                data_dir=prepared.cfg.data_dir,
                exclude_author=prepared.cfg.defaults.exclude_author,
                exclude_bots=prepared.cfg.defaults.exclude_bots,
            )
            truth_diags[policy_id] = diag
            truth_status_counts_by_policy[policy_id][diag.status.value] = (
                truth_status_counts_by_policy[policy_id].get(diag.status.value, 0) + 1
            )

        truth_diag = truth_diags[prepared.truth_primary_policy]
        truth_targets = (
            [] if truth_diag.selected_login is None else [truth_diag.selected_login]
        )
        truth_status_counts[truth_diag.status.value] = (
            truth_status_counts.get(truth_diag.status.value, 0) + 1
        )

        gate_metrics = per_pr_gate_metrics(
            repo=prepared.cfg.repo,
            pr_number=pr_number,
            cutoff=cutoff,
            data_dir=prepared.cfg.data_dir,
        )

        results_by_router: dict[str, tuple[object, object]] = {}
        if prepared.cfg.defaults.execution_mode == "parallel" and len(ordered_router_ids) > 1:
            workers = prepared.cfg.defaults.max_workers or len(ordered_router_ids)
            with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
                futures = [
                    pool.submit(
                        _collect_router_run,
                        prepared=prepared,
                        router_id=router_id,
                        pr_number=pr_number,
                        cutoff=cutoff,
                        inputs=inputs,
                    )
                    for router_id in ordered_router_ids
                ]
                for fut in futures:
                    router_id, result, router = fut.result()
                    results_by_router[router_id] = (result, router)
        else:
            for router_id in ordered_router_ids:
                _, result, router = _collect_router_run(
                    prepared=prepared,
                    router_id=router_id,
                    pr_number=pr_number,
                    cutoff=cutoff,
                    inputs=inputs,
                )
                results_by_router[router_id] = (result, router)

        per_router: dict[str, object] = {}
        for router_id in ordered_router_ids:
            result, router = results_by_router[router_id]
            feature_meta: dict[str, object] = {}

            predictor = getattr(router, "predictor", None)
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
                    feature_meta["feature_version"] = predictor.last_features[
                        "feature_version"
                    ]

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
                    repo=prepared.cfg.repo,
                    pr_number=pr_number,
                    cutoff=cutoff,
                    targets=truth_targets,
                ),
            )
            pr_metrics_by_policy: dict[str, PRMetrics] = {}
            for policy_id, diag in truth_diags.items():
                targets = [] if diag.selected_login is None else [diag.selected_login]
                pr_metrics_by_policy[policy_id] = per_pr_metrics(
                    result=result,
                    truth=TruthLabel(
                        repo=prepared.cfg.repo,
                        pr_number=pr_number,
                        cutoff=cutoff,
                        targets=targets,
                    ),
                )
            queue_metrics = per_pr_queue_metrics(
                result=result,
                baseline=router_id,
                cutoff=cutoff,
                data_dir=prepared.cfg.data_dir,
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
                    for pid in prepared.truth_policies
                },
                "queue": queue_metrics.model_dump(mode="json"),
            }

        row: dict[str, object] = {
            "repo": prepared.cfg.repo,
            "run_id": prepared.cfg.run_id,
            "pr_number": pr_number,
            "cutoff": cutoff.isoformat(),
            "truth_behavior": truth_targets,
            "truth_status": truth_diag.status.value,
            "truth_diagnostics": truth_diag.model_dump(mode="json"),
            "truth": {
                "version": "v1",
                "primary_policy": prepared.truth_primary_policy,
                "policies": {
                    pid: {
                        "targets": (
                            []
                            if truth_diags[pid].selected_login is None
                            else [truth_diags[pid].selected_login]
                        ),
                        "status": truth_diags[pid].status.value,
                        "diagnostics": truth_diags[pid].model_dump(mode="json"),
                        "policy_hash": prepared.truth_policies[pid].policy_hash,
                        "policy_source": prepared.truth_policies[pid].source,
                        "policy_source_ref": prepared.truth_policies[pid].source_ref,
                    }
                    for pid in prepared.truth_policies
                },
            },
            "gates": gate_metrics.model_dump(mode="json"),
            "routers": per_router,
            "baselines": per_router,
        }
        if repo_profile_row is not None:
            row["repo_profile"] = repo_profile_row
        prepared.store.append_jsonl("per_pr.jsonl", row)
        gate_rows.append(gate_metrics)

    return PerPrEvalStage(
        routing_rows_by_router=routing_rows_by_router,
        routing_rows_known_by_router=routing_rows_known_by_router,
        routing_rows_by_policy_router=routing_rows_by_policy_router,
        queue_rows_by_router=queue_rows_by_router,
        gate_rows=gate_rows,
        router_feature_meta=router_feature_meta,
        truth_status_counts=truth_status_counts,
        truth_status_counts_by_policy=truth_status_counts_by_policy,
    )
