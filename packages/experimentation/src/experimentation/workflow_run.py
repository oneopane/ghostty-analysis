from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from evaluation_harness.config import EvalDefaults, EvalRunConfig
from evaluation_harness.run_id import compute_run_id
from evaluation_harness.service import run as run_eval
from repo_routing.registry import RouterSpec, router_id_for_spec

from .workflow_artifacts import (
    _build_repo_profile_settings,
    _default_prefetch_summary,
    _prefetch_missing_artifacts,
)
from .workflow_helpers import (
    DEFAULT_PINNED_ARTIFACT_PATHS,
    _build_cohort_payload,
    _build_router_specs,
    _inline_cohort_overrides,
    _parse_dt_option,
    _read_json,
    _resolve_pr_cutoffs,
    _router_specs_from_spec,
    _spec_cohort_ref,
    _spec_from_inline,
    _validate_hashed_payload,
    _write_json,
)
from .workflow_reports import (
    EXPERIMENT_MANIFEST_FILENAME,
    _load_per_pr_rows,
    _load_report,
    _run_context_payload,
)
from .workflow_quality import (
    evaluate_promotion,
    evaluate_quality_gates,
    persist_report_post_processing,
)


def experiment_run(
    repo: str | None = typer.Option(None, help="Repository in owner/name format"),
    data_dir: str = typer.Option("data", help="Base directory for repo data"),
    run_id: str | None = typer.Option(None, help="Run id (default: computed)"),
    spec: str | None = typer.Option(None, help="Experiment spec JSON path"),
    cohort: str | None = typer.Option(None, help="Cohort JSON path"),
    pr: list[int] = typer.Option([], "--pr", help="Explicit PR number(s)"),
    start_at: str | None = typer.Option(
        None, "--from", "--start-at", help="ISO created_at window start"
    ),
    end_at: str | None = typer.Option(None, help="ISO created_at window end"),
    limit: int | None = typer.Option(None, help="Maximum PR count"),
    seed: int | None = typer.Option(None, help="Seed used when sampling with --limit"),
    cutoff_policy: str = typer.Option("created_at", help="Cutoff policy for inline mode"),
    router: list[str] = typer.Option([], "--router", help="Builtin router id(s)"),
    router_import: list[str] = typer.Option(
        [],
        "--router-import",
        help="Import-path router(s): pkg.mod:ClassOrFactory",
    ),
    router_config: list[str] = typer.Option(
        [],
        "--router-config",
        help="Router config path(s): router_id=path, name=path, or positional",
    ),
    allow_fetch_missing_artifacts: bool = typer.Option(
        False,
        help="Fetch missing pinned artifacts before evaluation",
    ),
):
    spec_path: Path | None = None
    spec_payload: dict[str, Any]
    if spec is not None:
        spec_path = Path(spec)
        spec_payload = _validate_hashed_payload(
            payload=_read_json(spec_path),
            kind="experiment_spec",
            path=spec_path,
        )
    else:
        spec_payload = {}

    locked_cohort_path: Path | None = None
    locked_cohort_hash: str | None = None
    spec_locks_cohort = False
    if spec_payload:
        locked_cohort_path, locked_cohort_hash, spec_locks_cohort = _spec_cohort_ref(
            spec_payload=spec_payload,
            spec_path=spec_path,
        )

    inline_conflicts = _inline_cohort_overrides(
        pr_numbers=list(pr),
        start_at=start_at,
        end_at=end_at,
        limit=limit,
        seed=seed,
        cutoff_policy=cutoff_policy,
    )
    if spec_locks_cohort and inline_conflicts:
        raise typer.BadParameter(
            "experiment spec locks cohort via spec.cohort, so inline cohort flags are not allowed: "
            + ", ".join(inline_conflicts)
            + ". Remove those flags or run without a locked cohort in spec."
        )

    cohort_path: Path | None = None
    cohort_payload: dict[str, Any]
    cli_cohort_payload: dict[str, Any] | None = None
    cli_cohort_path: Path | None = None
    if cohort is not None:
        cli_cohort_path = Path(cohort)
        cli_cohort_payload = _validate_hashed_payload(
            payload=_read_json(cli_cohort_path),
            kind="cohort",
            path=cli_cohort_path,
        )

    locked_cohort_payload: dict[str, Any] | None = None
    if locked_cohort_path is not None:
        locked_cohort_payload = _validate_hashed_payload(
            payload=_read_json(locked_cohort_path),
            kind="cohort",
            path=locked_cohort_path,
        )
        if (
            locked_cohort_hash is not None
            and str(locked_cohort_payload.get("hash") or "") != locked_cohort_hash
        ):
            raise typer.BadParameter(
                "experiment spec cohort hash does not match cohort file at spec.cohort.path: "
                f"{locked_cohort_path}"
            )

    if spec_locks_cohort:
        if locked_cohort_payload is not None:
            if cli_cohort_payload is not None and (
                str(cli_cohort_payload.get("hash") or "")
                != str(locked_cohort_payload.get("hash") or "")
            ):
                raise typer.BadParameter(
                    "--cohort does not match cohort locked by experiment spec. "
                    "Use the exact cohort from spec.cohort.path/hash or remove --cohort."
                )
            cohort_payload = locked_cohort_payload
            cohort_path = locked_cohort_path
        else:
            if cli_cohort_payload is None:
                raise typer.BadParameter(
                    "experiment spec locks cohort by hash but no cohort path was provided. "
                    "Pass --cohort <path> that matches spec.cohort.hash."
                )
            if (
                locked_cohort_hash is not None
                and str(cli_cohort_payload.get("hash") or "") != locked_cohort_hash
            ):
                raise typer.BadParameter(
                    "--cohort hash does not match experiment spec cohort hash."
                )
            cohort_payload = cli_cohort_payload
            cohort_path = cli_cohort_path
    else:
        if cli_cohort_payload is not None:
            cohort_payload = cli_cohort_payload
            cohort_path = cli_cohort_path
        else:
            inline_repo = repo
            if inline_repo is None and spec_payload:
                inline_repo = str(spec_payload.get("repo") or "") or None
            if inline_repo is None:
                raise typer.BadParameter(
                    "--repo is required when cohort is not provided and spec does not lock a cohort"
                )
            cohort_payload = _build_cohort_payload(
                repo=inline_repo,
                data_dir=data_dir,
                pr_numbers=list(pr),
                start_at=_parse_dt_option(start_at, option="--start-at"),
                end_at=_parse_dt_option(end_at, option="--end-at"),
                limit=limit,
                seed=seed,
                cutoff_policy=cutoff_policy,
            )

    if not spec_payload:
        inline_repo = repo or str(cohort_payload.get("repo") or "")
        if not inline_repo:
            raise typer.BadParameter("--repo is required when --spec is not provided")
        inline_router_specs = _build_router_specs(
            routers=list(router),
            router_imports=list(router_import),
            router_configs=list(router_config),
        )
        spec_payload = _spec_from_inline(
            repo=inline_repo,
            cohort_hash=str(cohort_payload.get("hash") or ""),
            cohort_path=cohort_path,
            cutoff_policy=cutoff_policy,
            strict_streaming_eval=True,
            top_k=5,
            router_specs=inline_router_specs,
            repo_profile_enabled=True,
            repo_profile_strict=True,
            allow_fetch_missing_artifacts=allow_fetch_missing_artifacts,
            artifact_paths=list(DEFAULT_PINNED_ARTIFACT_PATHS),
            critical_artifact_paths=[],
            llm_mode="replay",
            profile="audit",
        )

    repo_name = str(spec_payload.get("repo") or "")
    if not repo_name:
        raise typer.BadParameter("experiment spec is missing repo")
    if repo is not None and repo != repo_name:
        raise typer.BadParameter(f"--repo mismatch: {repo} != {repo_name}")
    if str(cohort_payload.get("repo") or "") != repo_name:
        raise typer.BadParameter("cohort repo does not match experiment spec repo")

    cohort_hash = str(cohort_payload.get("hash") or "")
    if not cohort_hash:
        raise typer.BadParameter("cohort payload missing hash")
    spec_cohort_hash = None
    spec_cohort_raw = spec_payload.get("cohort")
    if isinstance(spec_cohort_raw, dict) and isinstance(spec_cohort_raw.get("hash"), str):
        spec_cohort_hash = str(spec_cohort_raw.get("hash") or "") or None
    if spec_cohort_hash is not None and spec_cohort_hash != cohort_hash:
        raise typer.BadParameter(
            "cohort hash mismatch between cohort artifact and experiment spec.cohort.hash"
        )

    spec_profile_raw = spec_payload.get("repo_profile")
    spec_profile = spec_profile_raw if isinstance(spec_profile_raw, dict) else {}
    fetch_missing = allow_fetch_missing_artifacts or bool(
        spec_profile.get("allow_fetch_missing_artifacts", False)
    )

    pr_numbers = [int(x) for x in cohort_payload.get("pr_numbers") or []]
    if not pr_numbers:
        raise typer.BadParameter("cohort has no PR numbers")

    active_cutoff_policy = str(spec_payload.get("cutoff_policy") or "created_at")
    cutoffs = _resolve_pr_cutoffs(
        repo=repo_name,
        data_dir=data_dir,
        pr_numbers=pr_numbers,
        cutoff_policy=active_cutoff_policy,
        cohort_payload=cohort_payload,
        require_complete_from_cohort=True,
    )

    artifact_paths_raw = spec_profile.get("artifact_paths")
    if isinstance(artifact_paths_raw, list) and artifact_paths_raw:
        artifact_paths = [str(x) for x in artifact_paths_raw]
    else:
        artifact_paths = list(DEFAULT_PINNED_ARTIFACT_PATHS)

    prefetch_summary: dict[str, Any]
    if fetch_missing:
        prefetch_summary = _prefetch_missing_artifacts(
            repo=repo_name,
            data_dir=data_dir,
            pr_numbers=pr_numbers,
            cutoffs=cutoffs,
            artifact_paths=artifact_paths,
        )
    else:
        prefetch_summary = _default_prefetch_summary(artifact_paths=artifact_paths)

    router_specs = _router_specs_from_spec(spec_payload)
    if not router_specs:
        router_specs = [RouterSpec(type="builtin", name="mentions")]

    defaults = EvalDefaults(
        strict_streaming_eval=bool(spec_payload.get("strict_streaming_eval", True)),
        cutoff_policy=active_cutoff_policy,
        top_k=int(spec_payload.get("top_k", 5)),
        llm_mode=str(
            ((spec_payload.get("llm") or {}) if isinstance(spec_payload.get("llm"), dict) else {}).get("mode")
            or "replay"
        ),
    )
    cfg = EvalRunConfig(
        repo=repo_name,
        data_dir=data_dir,
        run_id=run_id or "run",
        defaults=defaults,
    )
    if run_id is None:
        cfg.run_id = compute_run_id(cfg=cfg)

    profile_settings = _build_repo_profile_settings(spec_payload)

    result = run_eval(
        cfg=cfg,
        pr_numbers=pr_numbers,
        router_specs=router_specs,
        repo_profile_settings=profile_settings,
        pr_cutoffs=cutoffs,
    )

    routers_for_run = [router_id_for_spec(s) for s in router_specs]
    try:
        report_payload = _load_report(repo=repo_name, run_id=cfg.run_id, data_dir=data_dir)
    except Exception:
        report_payload = {"kind": "eval_report", "version": "v0", "extra": {}}
    per_pr_rows = _load_per_pr_rows(repo=repo_name, run_id=cfg.run_id, data_dir=data_dir)
    if per_pr_rows and isinstance(report_payload, dict):
        quality_gates = evaluate_quality_gates(
            rows=per_pr_rows,
            report=report_payload,
            routers=routers_for_run,
        )
    else:
        quality_gates = {"all_pass": True, "gates": {}, "thresholds": {}}
    report_extra = report_payload.get("extra")
    if not isinstance(report_extra, dict):
        report_extra = {}
    primary_policy = str(report_extra.get("truth_primary_policy") or "first_approval_v1")
    promotion_eval = evaluate_promotion(
        rows=per_pr_rows,
        routers=routers_for_run,
        primary_policy=primary_policy,
        gate_all_pass=bool(quality_gates.get("all_pass")),
    )
    report_payload = persist_report_post_processing(
        repo=repo_name,
        run_id=cfg.run_id,
        data_dir=data_dir,
        report_payload=report_payload,
        quality_gates=quality_gates,
        promotion_evaluation=promotion_eval,
    )

    cohort_copy = result.run_dir / "cohort.json"
    spec_copy = result.run_dir / "experiment.json"
    _write_json(cohort_copy, cohort_payload)
    _write_json(spec_copy, spec_payload)

    context = _run_context_payload(
        repo=repo_name,
        run_id=cfg.run_id,
        cohort_path=cohort_path,
        spec_path=spec_path,
        cohort_payload=cohort_payload,
        spec_payload=spec_payload,
        router_specs=router_specs,
        cutoff_source="cohort_pr_cutoffs",
        pr_cutoffs=cutoffs,
        artifact_prefetch=prefetch_summary,
    )
    context["quality_gates"] = quality_gates
    context["promotion_evaluation"] = promotion_eval
    _write_json(result.run_dir / EXPERIMENT_MANIFEST_FILENAME, context)

    typer.echo(f"run_dir {result.run_dir}")
    typer.echo(f"cohort_hash {cohort_payload['hash']}")
    typer.echo(f"experiment_spec_hash {spec_payload['hash']}")
    typer.echo(f"quality_gates_pass {quality_gates.get('all_pass')}")

    profile_mode = str(spec_payload.get("profile") or "audit").strip().lower()
    if profile_mode == "audit" and not bool(quality_gates.get("all_pass")):
        raise typer.Exit(code=1)
