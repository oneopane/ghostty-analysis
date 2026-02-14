from __future__ import annotations

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any

import typer
from sdlc_core.hashing import stable_hash_json
from evaluation_harness.cutoff import cutoff_for_pr
from evaluation_harness.sampling import sample_pr_numbers_created_in_window
from repo_routing.api import (
    CODEOWNERS_PATH_CANDIDATES,
    DEFAULT_PINNED_ARTIFACT_PATHS,
    RouterSpec,
    build_router_specs as shared_build_router_specs,
    parse_dt_utc,
    pinned_artifact_path,
    require_dt_utc,
)

from .workflow_artifacts import (
    _build_repo_profile_settings,
    _default_prefetch_summary,
    _missing_artifact_paths,
    _prefetch_missing_artifacts,
)
from workflow.reports import (
    EXPERIMENT_MANIFEST_FILENAME,
    _delta,
    _load_per_pr_rows,
    _load_report,
    _load_run_context,
    _run_context_payload,
)


def _stable_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, indent=2) + "\n"


def _stable_hash_payload(payload: dict[str, Any]) -> str:
    clean = dict(payload)
    clean.pop("hash", None)
    return stable_hash_json(clean)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_stable_json(payload), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"invalid JSON: {path}") from exc
    if not isinstance(obj, dict):
        raise typer.BadParameter(f"expected JSON object: {path}")
    return obj


def _parse_dt_option(value: str | None, *, option: str) -> datetime | None:
    if value is None:
        return None
    try:
        dt = parse_dt_utc(value)
    except ValueError as exc:
        raise typer.BadParameter(f"invalid ISO timestamp for {option}: {value}") from exc
    if dt is None:
        return None
    return dt


def _iso_utc(dt: datetime) -> str:
    normalized = require_dt_utc(dt)
    return normalized.isoformat().replace("+00:00", "Z")


def _build_router_specs(
    *,
    routers: list[str],
    router_imports: list[str],
    router_configs: list[str],
) -> list[RouterSpec]:
    try:
        return shared_build_router_specs(
            routers=routers,
            router_imports=router_imports,
            router_configs=router_configs,
            stewards_config_required_message="--router-config is required when router includes stewards",
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _sample_prs(
    *,
    repo: str,
    data_dir: str,
    pr_numbers: list[int],
    start_at: datetime | None,
    end_at: datetime | None,
    limit: int | None,
    seed: int | None,
) -> list[int]:
    if pr_numbers:
        prs = sorted(set(int(x) for x in pr_numbers))
        if limit is not None:
            prs = prs[: int(limit)]
        return prs

    pool = sample_pr_numbers_created_in_window(
        repo=repo,
        data_dir=data_dir,
        start_at=start_at,
        end_at=end_at,
        limit=None,
    )
    if seed is not None and limit is not None and len(pool) > limit:
        rng = random.Random(seed)
        shuffled = list(pool)
        rng.shuffle(shuffled)
        pool = shuffled[: int(limit)]
    elif limit is not None:
        pool = pool[: int(limit)]

    prs = sorted(set(int(n) for n in pool))
    return prs


def _build_cohort_payload(
    *,
    repo: str,
    data_dir: str,
    pr_numbers: list[int],
    start_at: datetime | None,
    end_at: datetime | None,
    limit: int | None,
    seed: int | None,
    cutoff_policy: str,
) -> dict[str, Any]:
    selected = _sample_prs(
        repo=repo,
        data_dir=data_dir,
        pr_numbers=pr_numbers,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
        seed=seed,
    )
    if not selected:
        raise typer.BadParameter("no PRs selected for cohort")

    cutoffs = {
        str(n): _iso_utc(
            cutoff_for_pr(repo=repo, pr_number=n, data_dir=data_dir, policy=cutoff_policy)
        )
        for n in selected
    }
    payload: dict[str, Any] = {
        "kind": "cohort",
        "version": "v1",
        "repo": repo,
        "cutoff_policy": cutoff_policy,
        "filters": {
            "start_at": None if start_at is None else _iso_utc(start_at),
            "end_at": None if end_at is None else _iso_utc(end_at),
            "limit": limit,
            "seed": seed,
        },
        "pr_numbers": selected,
        "pr_cutoffs": cutoffs,
    }
    payload["hash"] = _stable_hash_payload(payload)
    return payload


def _validate_hashed_payload(
    *,
    payload: dict[str, Any],
    kind: str,
    path: Path | None = None,
) -> dict[str, Any]:
    if payload.get("kind") != kind:
        where = f" in {path}" if path is not None else ""
        raise typer.BadParameter(f"expected kind={kind!r}{where}")
    expected = payload.get("hash")
    if not isinstance(expected, str) or not expected:
        where = f" in {path}" if path is not None else ""
        raise typer.BadParameter(f"missing hash{where}")
    actual = _stable_hash_payload(payload)
    if actual != expected:
        where = f" in {path}" if path is not None else ""
        raise typer.BadParameter(
            f"hash mismatch{where}: expected {expected}, recomputed {actual}"
        )
    return payload


def _spec_from_inline(
    *,
    repo: str,
    cohort_hash: str | None,
    cohort_path: Path | None,
    cutoff_policy: str,
    strict_streaming_eval: bool,
    top_k: int,
    router_specs: list[RouterSpec],
    repo_profile_enabled: bool,
    repo_profile_strict: bool,
    allow_fetch_missing_artifacts: bool,
    artifact_paths: list[str],
    critical_artifact_paths: list[str],
    llm_mode: str,
    profile: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": "experiment_spec",
        "version": "v1",
        "repo": repo,
        "cohort": {
            "path": None if cohort_path is None else str(cohort_path),
            "hash": cohort_hash,
        },
        "cutoff_policy": cutoff_policy,
        "strict_streaming_eval": strict_streaming_eval,
        "top_k": int(top_k),
        "routers": [s.model_dump(mode="json") for s in router_specs],
        "repo_profile": {
            "enabled": repo_profile_enabled,
            "strict": repo_profile_strict,
            "allow_fetch_missing_artifacts": allow_fetch_missing_artifacts,
            "artifact_paths": sorted(set(artifact_paths), key=str.lower),
            "critical_artifact_paths": sorted(
                set(critical_artifact_paths), key=str.lower
            ),
        },
        "llm": {
            "mode": llm_mode,
        },
        "profile": profile,
        "feature_policy_mode": "v0",
        "tags": [],
        "notes": "",
    }
    payload["hash"] = _stable_hash_payload(payload)
    return payload


def _router_specs_from_spec(spec_payload: dict[str, Any]) -> list[RouterSpec]:
    raw = spec_payload.get("routers")
    if not isinstance(raw, list) or not raw:
        return [RouterSpec(type="builtin", name="mentions")]
    llm_raw = spec_payload.get("llm")
    llm_mode = "replay"
    if isinstance(llm_raw, dict):
        llm_mode = str(llm_raw.get("mode") or "replay").strip().lower()

    specs: list[RouterSpec] = []
    for item in raw:
        if not isinstance(item, dict):
            raise typer.BadParameter("invalid experiment spec routers entry")
        name = str(item.get("name") or "")
        config_path = (
            None
            if item.get("config_path") is None
            else str(item.get("config_path"))
        )
        if str(item.get("type") or "") == "builtin" and name == "llm_rerank" and not config_path:
            config_path = llm_mode
        specs.append(
            RouterSpec(
                type=str(item.get("type") or ""),
                name=name,
                import_path=(
                    None
                    if item.get("import_path") is None
                    else str(item.get("import_path"))
                ),
                config_path=config_path,
            )
        )
    return specs


def _spec_cohort_ref(
    *,
    spec_payload: dict[str, Any],
    spec_path: Path | None,
) -> tuple[Path | None, str | None, bool]:
    raw = spec_payload.get("cohort")
    if not isinstance(raw, dict):
        return None, None, False

    ref_hash_raw = raw.get("hash")
    ref_hash = str(ref_hash_raw).strip() if isinstance(ref_hash_raw, str) else None
    if ref_hash == "":
        ref_hash = None

    ref_path_raw = raw.get("path")
    ref_path: Path | None = None
    if isinstance(ref_path_raw, str) and ref_path_raw.strip():
        p = Path(ref_path_raw.strip())
        if not p.is_absolute() and spec_path is not None:
            p = spec_path.parent / p
        ref_path = p

    return ref_path, ref_hash, (ref_path is not None or ref_hash is not None)


def _inline_cohort_overrides(
    *,
    pr_numbers: list[int],
    start_at: str | None,
    end_at: str | None,
    limit: int | None,
    seed: int | None,
    cutoff_policy: str,
) -> list[str]:
    flags: list[str] = []
    if pr_numbers:
        flags.append("--pr")
    if start_at is not None:
        flags.append("--from/--start-at")
    if end_at is not None:
        flags.append("--end-at")
    if limit is not None:
        flags.append("--limit")
    if seed is not None:
        flags.append("--seed")
    if cutoff_policy != "created_at":
        flags.append("--cutoff-policy")
    return flags


def _resolve_pr_cutoffs(
    *,
    repo: str,
    data_dir: str,
    pr_numbers: list[int],
    cutoff_policy: str,
    cohort_payload: dict[str, Any] | None,
    require_complete_from_cohort: bool,
) -> dict[int, datetime]:
    out: dict[int, datetime] = {}
    by_pr: dict[str, Any] = {}
    if cohort_payload is not None and isinstance(cohort_payload.get("pr_cutoffs"), dict):
        by_pr = cohort_payload["pr_cutoffs"]  # type: ignore[assignment]

    missing_from_cohort: list[int] = []
    for n in pr_numbers:
        raw = by_pr.get(str(n))
        if raw is not None:
            dt = parse_dt_utc(raw)
            if dt is None:
                raise typer.BadParameter(f"invalid cohort cutoff for PR {n}: {raw}")
            out[n] = dt
            continue

        if require_complete_from_cohort and cohort_payload is not None:
            missing_from_cohort.append(n)
            continue

        out[n] = cutoff_for_pr(
            repo=repo,
            pr_number=n,
            data_dir=data_dir,
            policy=cutoff_policy,
        )

    if missing_from_cohort:
        listed = ", ".join(str(n) for n in missing_from_cohort)
        raise typer.BadParameter(
            "cohort is missing cutoff entries for PR(s): "
            f"{listed}. Regenerate cohort.json via `repo cohort create ...` to lock cutoffs."
        )

    return out
