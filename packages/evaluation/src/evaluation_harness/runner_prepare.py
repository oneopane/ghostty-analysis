from __future__ import annotations

from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

from repo_routing.registry import RouterSpec, load_router, router_id_for_spec
from repo_routing.time import require_dt_utc
from sdlc_core.store import FileArtifactStore, FileRunStore

from .config import EvalRunConfig
from .cutoff import cutoff_for_pr
from .db import RepoDb
from .paths import repo_eval_run_dir
from .runner_models import PreparedEvalStage
from .store.filesystem import FilesystemStore
from .truth_policy import ResolvedTruthPolicy, resolve_truth_policies


def normalize_router_specs(
    *,
    router_specs: list[RouterSpec] | None,
    router_config_path: str | Path | None,
) -> list[RouterSpec]:
    if router_specs:
        specs = [s.model_copy() for s in router_specs]
    else:
        specs = [
            RouterSpec(type="builtin", name="mentions"),
            RouterSpec(type="builtin", name="popularity"),
            RouterSpec(type="builtin", name="codeowners"),
        ]

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


def normalize_pr_cutoffs(
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


def prepare_eval_stage(
    *,
    cfg: EvalRunConfig,
    pr_numbers: list[int],
    router_specs: list[RouterSpec] | None,
    router_config_path: str | Path | None,
    pr_cutoffs: dict[int | str, datetime] | None,
) -> PreparedEvalStage:
    specs = normalize_router_specs(
        router_specs=router_specs,
        router_config_path=router_config_path,
    )
    router_ids = [router_id_for_spec(s) for s in specs]
    routers_by_id = {router_id_for_spec(spec): load_router(spec) for spec in specs}
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
    artifact_store = FileArtifactStore(root=run_dir)
    run_store = FileRunStore(root=run_dir)

    db = RepoDb(repo=cfg.repo, data_dir=cfg.data_dir)
    conn = db.connect()
    try:
        db_max_event_occurred_at = db.max_event_occurred_at(conn)
        db_max_watermark_updated_at = db.max_watermark_updated_at(conn)
    finally:
        conn.close()

    cutoffs, cutoff_source = normalize_pr_cutoffs(
        cfg=cfg,
        pr_numbers=pr_numbers,
        pr_cutoffs=pr_cutoffs,
    )
    ordered_pr_numbers = sorted(pr_numbers, key=lambda n: (cutoffs[n], n))

    stale_cutoff_note: str | None = None
    if db_max_event_occurred_at is not None:
        stale_cutoff_prs = [
            n for n in ordered_pr_numbers if cutoffs[n] > db_max_event_occurred_at
        ]
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
    truth_primary_policy = cfg.defaults.resolved_truth_primary_policy()
    if truth_primary_policy not in truth_policies:
        raise ValueError(
            f"truth_primary_policy is not active: {truth_primary_policy}; "
            f"active={list(truth_policies)}"
        )

    return PreparedEvalStage(
        cfg=cfg,
        specs=specs,
        router_ids=router_ids,
        routers_by_id=routers_by_id,
        package_versions=package_versions,
        generated_at=generated_at,
        run_dir=run_dir,
        store=store,
        artifact_store=artifact_store,
        run_store=run_store,
        db_max_event_occurred_at=db_max_event_occurred_at,
        db_max_watermark_updated_at=db_max_watermark_updated_at,
        cutoffs=cutoffs,
        cutoff_source=cutoff_source,
        ordered_pr_numbers=ordered_pr_numbers,
        stale_cutoff_note=stale_cutoff_note,
        truth_window_seconds=truth_window_seconds,
        truth_policies=truth_policies,
        truth_primary_policy=truth_primary_policy,
    )
