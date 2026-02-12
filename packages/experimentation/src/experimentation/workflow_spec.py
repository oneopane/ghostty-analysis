from __future__ import annotations

from pathlib import Path

import typer

from .workflow_helpers import (
    DEFAULT_PINNED_ARTIFACT_PATHS,
    _build_router_specs,
    _read_json,
    _spec_from_inline,
    _validate_hashed_payload,
    _write_json,
)


def experiment_init(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    output: str = typer.Option("experiment.json", help="Output experiment spec path"),
    cohort: str | None = typer.Option(None, help="Optional cohort JSON path"),
    cutoff_policy: str = typer.Option("created_at", help="Cutoff policy"),
    strict_streaming_eval: bool = typer.Option(
        True,
        "--strict-streaming-eval/--no-strict-streaming-eval",
        help="Fail when DB horizon is before any PR cutoff",
    ),
    profile: str = typer.Option(
        "audit",
        help="Run profile used for gate enforcement (audit|standard)",
    ),
    llm_mode: str = typer.Option(
        "replay",
        help="LLM run mode (off|live|replay)",
    ),
    top_k: int = typer.Option(5, help="Router top-k"),
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
    enable_repo_profile: bool = typer.Option(
        True,
        "--enable-repo-profile/--disable-repo-profile",
        help="Build per-PR repo profile during experiment runs",
    ),
    strict_repo_profile: bool = typer.Option(
        True,
        "--strict-repo-profile/--no-strict-repo-profile",
        help="Fail when required repo-profile coverage is missing",
    ),
    allow_fetch_missing_artifacts: bool = typer.Option(
        False,
        help="Permit fetching missing pinned artifacts during run",
    ),
    artifact_path: list[str] = typer.Option(
        list(DEFAULT_PINNED_ARTIFACT_PATHS),
        "--artifact-path",
        help="Pinned artifact path allowlist (repeatable)",
    ),
    critical_artifact_path: list[str] = typer.Option(
        [],
        "--critical-artifact-path",
        help="Critical pinned artifact path(s) (repeatable)",
    ),
):
    cohort_path: Path | None = None
    cohort_hash: str | None = None
    if cohort is not None:
        cohort_path = Path(cohort)
        cohort_payload = _validate_hashed_payload(
            payload=_read_json(cohort_path),
            kind="cohort",
            path=cohort_path,
        )
        cohort_hash = str(cohort_payload.get("hash"))

    specs = _build_router_specs(
        routers=list(router),
        router_imports=list(router_import),
        router_configs=list(router_config),
    )
    payload = _spec_from_inline(
        repo=repo,
        cohort_hash=cohort_hash,
        cohort_path=cohort_path,
        cutoff_policy=cutoff_policy,
        strict_streaming_eval=strict_streaming_eval,
        top_k=top_k,
        router_specs=specs,
        repo_profile_enabled=enable_repo_profile,
        repo_profile_strict=strict_repo_profile,
        allow_fetch_missing_artifacts=allow_fetch_missing_artifacts,
        artifact_paths=list(artifact_path),
        critical_artifact_paths=list(critical_artifact_path),
        llm_mode=llm_mode,
        profile=profile,
    )
    out = Path(output)
    _write_json(out, payload)
    typer.echo(f"wrote {out}")
    typer.echo(f"experiment_spec_hash {payload['hash']}")
