from __future__ import annotations

import hashlib
import json
import random
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
from evaluation_harness.cli.app import (
    explain as eval_explain_cmd,
)
from evaluation_harness.cli.app import list_runs as eval_list_runs_cmd
from evaluation_harness.cli.app import show as eval_show_cmd
from evaluation_harness.config import EvalDefaults, EvalRunConfig
from evaluation_harness.cutoff import cutoff_for_pr
from evaluation_harness.paths import (
    eval_per_pr_jsonl_path,
    eval_report_json_path,
    repo_eval_run_dir,
)
from evaluation_harness.run_id import compute_run_id
from evaluation_harness.runner import RepoProfileRunSettings, run_streaming_eval
from evaluation_harness.sampling import sample_pr_numbers_created_in_window
from gh_history_ingestion.repo_artifacts.fetcher import fetch_pinned_repo_artifacts_sync
from repo_routing.artifacts.writer import ArtifactWriter
from repo_routing.history.reader import HistoryReader
from repo_routing.repo_profile.builder import build_repo_profile
from repo_routing.repo_profile.storage import (
    CODEOWNERS_PATH_CANDIDATES,
    DEFAULT_PINNED_ARTIFACT_PATHS,
    pinned_artifact_path,
)
from repo_routing.registry import RouterSpec, router_id_for_spec
from repo_routing.time import parse_dt_utc, require_dt_utc


cohort_app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)
experiment_app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)
profile_app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)

_VALID_ROUTERS = {"mentions", "popularity", "codeowners", "stewards"}
_EXPERIMENT_MANIFEST_FILENAME = "experiment_manifest.json"


def _stable_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, indent=2) + "\n"


def _stable_hash_payload(payload: dict[str, Any]) -> str:
    clean = dict(payload)
    clean.pop("hash", None)
    data = json.dumps(clean, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


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


def _normalize_builtin_routers(values: list[str], *, option_name: str) -> list[str]:
    normalized = [v.strip().lower() for v in values if v.strip()]
    unknown = sorted({b for b in normalized if b not in _VALID_ROUTERS})
    if unknown:
        valid = ", ".join(sorted(_VALID_ROUTERS))
        raise typer.BadParameter(
            f"unknown {option_name}(s): {', '.join(unknown)}. valid: {valid}"
        )
    return normalized


def _apply_router_configs(
    *,
    specs: list[RouterSpec],
    router_configs: list[str],
) -> list[RouterSpec]:
    if not router_configs:
        return specs

    keyed = [c for c in router_configs if "=" in c]
    positional = [c for c in router_configs if "=" not in c]
    out = [s.model_copy() for s in specs]

    if keyed:
        mapping: dict[str, str] = {}
        for item in keyed:
            key, value = item.split("=", 1)
            if not key.strip() or not value.strip():
                raise typer.BadParameter(f"invalid --router-config pair: {item}")
            mapping[key.strip()] = value.strip()

        for i, spec in enumerate(out):
            rid = router_id_for_spec(spec)
            if rid in mapping:
                out[i] = spec.model_copy(update={"config_path": mapping[rid]})
            elif spec.name in mapping:
                out[i] = spec.model_copy(update={"config_path": mapping[spec.name]})

    if positional:
        if len(positional) > len(out):
            raise typer.BadParameter("too many --router-config values for routers")
        for i, cfg in enumerate(positional):
            out[i] = out[i].model_copy(update={"config_path": cfg})

    return out


def _build_router_specs(
    *,
    routers: list[str],
    router_imports: list[str],
    router_configs: list[str],
) -> list[RouterSpec]:
    builtin = _normalize_builtin_routers(routers, option_name="router")
    specs: list[RouterSpec] = [RouterSpec(type="builtin", name=name) for name in builtin]
    specs.extend(
        [
            RouterSpec(type="import_path", name=import_path, import_path=import_path)
            for import_path in router_imports
        ]
    )
    if not specs:
        specs = [RouterSpec(type="builtin", name="mentions")]
    specs = _apply_router_configs(specs=specs, router_configs=router_configs)

    for spec in specs:
        if spec.type == "builtin" and spec.name == "stewards":
            if spec.config_path is None:
                raise typer.BadParameter(
                    "--router-config is required when router includes stewards"
                )
            p = Path(spec.config_path)
            if not p.exists():
                raise typer.BadParameter(f"router config path does not exist: {p}")
    return specs


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
    specs: list[RouterSpec] = []
    for item in raw:
        if not isinstance(item, dict):
            raise typer.BadParameter("invalid experiment spec routers entry")
        specs.append(
            RouterSpec(
                type=str(item.get("type") or ""),
                name=str(item.get("name") or ""),
                import_path=(
                    None
                    if item.get("import_path") is None
                    else str(item.get("import_path"))
                ),
                config_path=(
                    None
                    if item.get("config_path") is None
                    else str(item.get("config_path"))
                ),
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


def _missing_artifact_paths(
    *,
    repo: str,
    data_dir: str,
    base_sha: str,
    artifact_paths: list[str],
) -> list[str]:
    missing: list[str] = []
    for rel in artifact_paths:
        p = pinned_artifact_path(
            repo_full_name=repo,
            base_sha=base_sha,
            relative_path=rel,
            data_dir=data_dir,
        )
        if not p.exists():
            missing.append(rel)
    return sorted(set(missing), key=str.lower)


def _prefetch_missing_artifacts(
    *,
    repo: str,
    data_dir: str,
    pr_numbers: list[int],
    cutoffs: dict[int, datetime],
    artifact_paths: list[str],
) -> dict[str, Any]:
    owner, name = repo.split("/", 1)
    seen_base_shas: set[str] = set()
    events: list[dict[str, Any]] = []

    with HistoryReader(repo_full_name=repo, data_dir=data_dir) as reader:
        for pr_number in pr_numbers:
            snapshot = reader.pull_request_snapshot(number=pr_number, as_of=cutoffs[pr_number])
            base_sha = snapshot.base_sha
            if not base_sha or base_sha in seen_base_shas:
                continue
            seen_base_shas.add(base_sha)

            missing = _missing_artifact_paths(
                repo=repo,
                data_dir=data_dir,
                base_sha=base_sha,
                artifact_paths=artifact_paths,
            )
            if not missing:
                continue

            manifest = fetch_pinned_repo_artifacts_sync(
                repo_full_name=repo,
                base_sha=base_sha,
                data_dir=data_dir,
                paths=missing,
            )
            manifest_path = (
                Path(data_dir)
                / "github"
                / owner
                / name
                / "repo_artifacts"
                / base_sha
                / "manifest.json"
            )

            events.append(
                {
                    "repo": repo,
                    "trigger_pr_number": pr_number,
                    "base_sha": base_sha,
                    "requested_paths": sorted(set(missing), key=str.lower),
                    "source": {
                        "provider": "github_contents_api",
                        "repo": repo,
                        "ref": base_sha,
                        "endpoint_template": "/repos/{owner}/{repo}/contents/{path}?ref={ref}",
                    },
                    "manifest_path": str(manifest_path),
                    "fetched_at": manifest.fetched_at,
                    "fetched_files": [
                        {
                            "path": f.path,
                            "content_sha256": f.content_sha256,
                            "size_bytes": f.size_bytes,
                            "detected_type": f.detected_type,
                            "blob_sha": f.blob_sha,
                            "source_url": f.source_url,
                            "git_url": f.git_url,
                            "download_url": f.download_url,
                        }
                        for f in sorted(manifest.files, key=lambda x: x.path.lower())
                    ],
                    "missing_after_fetch": sorted(
                        set(manifest.missing),
                        key=str.lower,
                    ),
                }
            )

    events.sort(key=lambda e: str(e.get("base_sha") or "").lower())
    return {
        "enabled": True,
        "network_used": bool(events),
        "requested_artifact_paths": sorted(set(artifact_paths), key=str.lower),
        "events": events,
    }


def _build_repo_profile_settings(spec_payload: dict[str, Any]) -> RepoProfileRunSettings | None:
    raw = spec_payload.get("repo_profile")
    if not isinstance(raw, dict):
        raw = {}
    enabled = bool(raw.get("enabled", True))
    if not enabled:
        return None
    artifact_paths = raw.get("artifact_paths")
    if not isinstance(artifact_paths, list) or not artifact_paths:
        artifact_paths = list(DEFAULT_PINNED_ARTIFACT_PATHS)
    critical = raw.get("critical_artifact_paths")
    if not isinstance(critical, list):
        critical = []
    return RepoProfileRunSettings(
        strict=bool(raw.get("strict", True)),
        artifact_paths=tuple(str(p) for p in artifact_paths),
        critical_artifact_paths=tuple(str(p) for p in critical),
    )


def _run_context_payload(
    *,
    repo: str,
    run_id: str,
    cohort_path: Path | None,
    spec_path: Path | None,
    cohort_payload: dict[str, Any],
    spec_payload: dict[str, Any],
    router_specs: list[RouterSpec],
    cutoff_source: str,
    pr_cutoffs: dict[int, datetime],
    artifact_prefetch: dict[str, Any],
) -> dict[str, Any]:
    return {
        "kind": "experiment_manifest",
        "version": "v1",
        "repo": repo,
        "run_id": run_id,
        "cohort_hash": cohort_payload["hash"],
        "experiment_spec_hash": spec_payload["hash"],
        "cohort_source_path": None if cohort_path is None else str(cohort_path),
        "spec_source_path": None if spec_path is None else str(spec_path),
        "cutoff_source": cutoff_source,
        "pr_cutoffs": {str(n): _iso_utc(pr_cutoffs[n]) for n in sorted(pr_cutoffs)},
        "artifact_prefetch": artifact_prefetch,
        "routers": [router_id_for_spec(s) for s in router_specs],
    }


def _load_run_context(run_dir: Path) -> dict[str, Any]:
    p = run_dir / _EXPERIMENT_MANIFEST_FILENAME
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _load_per_pr_rows(*, repo: str, run_id: str, data_dir: str) -> list[dict[str, Any]]:
    p = eval_per_pr_jsonl_path(repo_full_name=repo, data_dir=data_dir, run_id=run_id)
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _load_report(*, repo: str, run_id: str, data_dir: str) -> dict[str, Any]:
    p = eval_report_json_path(repo_full_name=repo, data_dir=data_dir, run_id=run_id)
    if not p.exists():
        raise typer.BadParameter(f"missing report.json for run {run_id}: {p}")
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise typer.BadParameter(f"invalid report.json for run {run_id}: {p}")
    return raw


def _delta(a: object, b: object) -> str:
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return "n/a"
    return f"{float(b) - float(a):+.4f}"


@cohort_app.command("create")
def cohort_create(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    output: str = typer.Option("cohort.json", help="Output cohort JSON path"),
    data_dir: str = typer.Option("data", help="Base directory for repo data"),
    pr: list[int] = typer.Option([], "--pr", help="Explicit PR number(s)"),
    start_at: str | None = typer.Option(
        None, "--from", "--start-at", help="ISO created_at window start"
    ),
    end_at: str | None = typer.Option(None, help="ISO created_at window end"),
    limit: int | None = typer.Option(None, help="Maximum PR count"),
    seed: int | None = typer.Option(None, help="Seed used when sampling with --limit"),
    cutoff_policy: str = typer.Option("created_at", help="Cutoff policy"),
):
    payload = _build_cohort_payload(
        repo=repo,
        data_dir=data_dir,
        pr_numbers=list(pr),
        start_at=_parse_dt_option(start_at, option="--start-at"),
        end_at=_parse_dt_option(end_at, option="--end-at"),
        limit=limit,
        seed=seed,
        cutoff_policy=cutoff_policy,
    )
    out = Path(output)
    _write_json(out, payload)
    typer.echo(f"wrote {out}")
    typer.echo(f"cohort_hash {payload['hash']}")
    typer.echo(f"pr_count {len(payload['pr_numbers'])}")


@experiment_app.command("init")
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
    )
    out = Path(output)
    _write_json(out, payload)
    typer.echo(f"wrote {out}")
    typer.echo(f"experiment_spec_hash {payload['hash']}")


@experiment_app.command("run")
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
        prefetch_summary = {
            "enabled": False,
            "network_used": False,
            "requested_artifact_paths": sorted(set(artifact_paths), key=str.lower),
            "events": [],
        }

    router_specs = _router_specs_from_spec(spec_payload)
    if not router_specs:
        router_specs = [RouterSpec(type="builtin", name="mentions")]

    defaults = EvalDefaults(
        strict_streaming_eval=bool(spec_payload.get("strict_streaming_eval", True)),
        cutoff_policy=active_cutoff_policy,
        top_k=int(spec_payload.get("top_k", 5)),
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

    result = run_streaming_eval(
        cfg=cfg,
        pr_numbers=pr_numbers,
        router_specs=router_specs,
        repo_profile_settings=profile_settings,
        pr_cutoffs=cutoffs,
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
    _write_json(result.run_dir / _EXPERIMENT_MANIFEST_FILENAME, context)

    typer.echo(f"run_dir {result.run_dir}")
    typer.echo(f"cohort_hash {cohort_payload['hash']}")
    typer.echo(f"experiment_spec_hash {spec_payload['hash']}")


@experiment_app.command("show")
def experiment_show(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    run_id: str = typer.Option(..., help="Evaluation run id"),
    data_dir: str = typer.Option("data", help="Base directory for repo data"),
):
    eval_show_cmd(repo=repo, run_id=run_id, data_dir=data_dir)


@experiment_app.command("list")
def experiment_list(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    data_dir: str = typer.Option("data", help="Base directory for repo data"),
):
    eval_list_runs_cmd(repo=repo, data_dir=data_dir)


@experiment_app.command("explain")
def experiment_explain(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    run_id: str = typer.Option(..., help="Evaluation run id"),
    pr_number: int = typer.Option(..., "--pr", help="Pull request number"),
    baseline: str | None = typer.Option(None, help="Router id (deprecated name)"),
    router: str | None = typer.Option(None, help="Router id"),
    policy: str | None = typer.Option(None, "--policy", help="Truth policy id"),
    data_dir: str = typer.Option("data", help="Base directory for repo data"),
):
    eval_explain_cmd(
        repo=repo,
        run_id=run_id,
        pr_number=pr_number,
        baseline=baseline,
        router=router,
        policy=policy,
        data_dir=data_dir,
    )


@experiment_app.command("diff")
def experiment_diff(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    run_a: str = typer.Option(..., "--run-a", help="Left run id"),
    run_b: str = typer.Option(..., "--run-b", help="Right run id"),
    data_dir: str = typer.Option("data", help="Base directory for repo data"),
    force: bool = typer.Option(
        False,
        "--force",
        help="Allow comparing runs with missing or mismatched cohort hashes",
    ),
):
    run_a_dir = repo_eval_run_dir(repo_full_name=repo, data_dir=data_dir, run_id=run_a)
    run_b_dir = repo_eval_run_dir(repo_full_name=repo, data_dir=data_dir, run_id=run_b)
    a_context = _load_run_context(run_a_dir)
    b_context = _load_run_context(run_b_dir)
    a_hash = a_context.get("cohort_hash")
    b_hash = b_context.get("cohort_hash")

    if not force:
        if not isinstance(a_hash, str) or not isinstance(b_hash, str):
            raise typer.BadParameter(
                "missing cohort hash in one or both runs; re-run with --force"
            )
        if a_hash != b_hash:
            raise typer.BadParameter(
                f"cohort hash mismatch: {a_hash} != {b_hash}. Use --force to override."
            )

    report_a = _load_report(repo=repo, run_id=run_a, data_dir=data_dir)
    report_b = _load_report(repo=repo, run_id=run_b, data_dir=data_dir)
    rows_a = _load_per_pr_rows(repo=repo, run_id=run_a, data_dir=data_dir)
    rows_b = _load_per_pr_rows(repo=repo, run_id=run_b, data_dir=data_dir)
    prs_a = {int(r.get("pr_number")) for r in rows_a if isinstance(r.get("pr_number"), int)}
    prs_b = {int(r.get("pr_number")) for r in rows_b if isinstance(r.get("pr_number"), int)}
    shared_prs = sorted(prs_a & prs_b)

    typer.echo(f"repo {repo}")
    typer.echo(f"run_a {run_a}")
    typer.echo(f"run_b {run_b}")
    typer.echo(f"cohort_hash_a {a_hash}")
    typer.echo(f"cohort_hash_b {b_hash}")
    typer.echo(f"shared_prs {len(shared_prs)}")

    routing_a = report_a.get("routing_agreement")
    routing_b = report_b.get("routing_agreement")
    if not isinstance(routing_a, dict) or not isinstance(routing_b, dict):
        raise typer.BadParameter("missing routing_agreement in one or both reports")
    common = sorted(set(routing_a.keys()) & set(routing_b.keys()), key=str.lower)
    if not common:
        typer.echo("no overlapping routers")
        raise typer.Exit(code=0)

    for rid in common:
        ra = routing_a.get(rid) or {}
        rb = routing_b.get(rid) or {}
        typer.echo(f"router {rid}")
        typer.echo(f"  hit_at_1 {ra.get('hit_at_1')} -> {rb.get('hit_at_1')} ({_delta(ra.get('hit_at_1'), rb.get('hit_at_1'))})")
        typer.echo(f"  hit_at_3 {ra.get('hit_at_3')} -> {rb.get('hit_at_3')} ({_delta(ra.get('hit_at_3'), rb.get('hit_at_3'))})")
        typer.echo(f"  hit_at_5 {ra.get('hit_at_5')} -> {rb.get('hit_at_5')} ({_delta(ra.get('hit_at_5'), rb.get('hit_at_5'))})")
        typer.echo(f"  mrr {ra.get('mrr')} -> {rb.get('mrr')} ({_delta(ra.get('mrr'), rb.get('mrr'))})")


def doctor(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    data_dir: str = typer.Option("data", help="Base directory for repo data"),
    cohort: str | None = typer.Option(None, help="Optional cohort JSON path"),
    pr: list[int] = typer.Option([], "--pr", help="Explicit PR number(s)"),
    start_at: str | None = typer.Option(
        None, "--from", "--start-at", help="ISO created_at window start"
    ),
    end_at: str | None = typer.Option(None, help="ISO created_at window end"),
    limit: int | None = typer.Option(None, help="Maximum PR count"),
    cutoff_policy: str = typer.Option("created_at", help="Cutoff policy"),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Exit non-zero on stale-cutoff or profile-coverage issues",
    ),
):
    cohort_payload: dict[str, Any] | None = None
    selected_prs: list[int]
    if cohort is not None:
        cpath = Path(cohort)
        cohort_payload = _validate_hashed_payload(
            payload=_read_json(cpath),
            kind="cohort",
            path=cpath,
        )
        if str(cohort_payload.get("repo") or "") != repo:
            raise typer.BadParameter("cohort repo mismatch")
        selected_prs = [int(x) for x in cohort_payload.get("pr_numbers") or []]
    else:
        selected_prs = _sample_prs(
            repo=repo,
            data_dir=data_dir,
            pr_numbers=list(pr),
            start_at=_parse_dt_option(start_at, option="--start-at"),
            end_at=_parse_dt_option(end_at, option="--end-at"),
            limit=limit,
            seed=None,
        )

    if not selected_prs:
        raise typer.BadParameter("no PRs selected")

    cutoffs = _resolve_pr_cutoffs(
        repo=repo,
        data_dir=data_dir,
        pr_numbers=selected_prs,
        cutoff_policy=cutoff_policy,
        cohort_payload=cohort_payload,
        require_complete_from_cohort=False,
    )

    owner, name = repo.split("/", 1)
    db_path = Path(data_dir) / "github" / owner / name / "history.sqlite"
    if not db_path.exists():
        raise typer.BadParameter(f"missing DB: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("select max(occurred_at) as max_at from events").fetchone()
        db_max_event = None if row is None else parse_dt_utc(row["max_at"])
        try:
            gap_rows = conn.execute(
                """
                select resource, count(*) as n
                from ingestion_gaps
                group by resource
                order by resource asc
                """
            ).fetchall()
        except sqlite3.OperationalError:
            gap_rows = []
        try:
            qa_row = conn.execute(
                "select summary_json from qa_reports order by id desc limit 1"
            ).fetchone()
        except sqlite3.OperationalError:
            qa_row = None
    finally:
        conn.close()

    stale_prs: list[int] = []
    if db_max_event is not None:
        stale_prs = [n for n in selected_prs if cutoffs[n] > db_max_event]

    codeowners_present = 0
    codeowners_missing: list[int] = []
    profile_missing_base_sha: list[int] = []
    with HistoryReader(repo_full_name=repo, data_dir=data_dir) as reader:
        for n in selected_prs:
            snap = reader.pull_request_snapshot(number=n, as_of=cutoffs[n])
            base_sha = snap.base_sha
            if not base_sha:
                profile_missing_base_sha.append(n)
                codeowners_missing.append(n)
                continue
            found = False
            for rel in CODEOWNERS_PATH_CANDIDATES:
                p = pinned_artifact_path(
                    repo_full_name=repo,
                    base_sha=base_sha,
                    relative_path=rel,
                    data_dir=data_dir,
                )
                if p.exists():
                    found = True
                    break
            if found:
                codeowners_present += 1
            else:
                codeowners_missing.append(n)

    qa_summary = None
    if qa_row is not None and qa_row["summary_json"]:
        try:
            qa_summary = json.loads(str(qa_row["summary_json"]))
        except Exception:
            qa_summary = None

    typer.echo(f"repo {repo}")
    typer.echo(f"pr_count {len(selected_prs)}")
    typer.echo(f"db_path {db_path}")
    typer.echo(f"db_max_event_occurred_at {None if db_max_event is None else _iso_utc(db_max_event)}")
    typer.echo(f"stale_cutoff_prs {len(stale_prs)}")
    if stale_prs:
        typer.echo("stale_cutoff_pr_list " + ",".join(str(n) for n in stale_prs))
    typer.echo(f"codeowners_present {codeowners_present}")
    typer.echo(f"codeowners_missing {len(codeowners_missing)}")
    if codeowners_missing:
        typer.echo("codeowners_missing_prs " + ",".join(str(n) for n in codeowners_missing))
    typer.echo(f"profile_missing_base_sha {len(profile_missing_base_sha)}")
    if gap_rows:
        typer.echo(
            "ingestion_gaps "
            + ", ".join(f"{str(r['resource'])}:{int(r['n'])}" for r in gap_rows)
        )
    else:
        typer.echo("ingestion_gaps none")
    if qa_summary is not None:
        typer.echo(
            "qa_total_gaps " + str(qa_summary.get("total_gaps"))
        )

    issues = 0
    if stale_prs:
        issues += 1
    if codeowners_missing:
        issues += 1
    if strict and issues > 0:
        raise typer.Exit(code=1)


@profile_app.command("build")
def profile_build(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    data_dir: str = typer.Option("data", help="Base directory for repo data"),
    run_id: str | None = typer.Option(None, help="Run id for profile artifacts"),
    pr: list[int] = typer.Option([], "--pr", help="Explicit PR number(s)"),
    start_at: str | None = typer.Option(
        None, "--from", "--start-at", help="ISO created_at window start"
    ),
    end_at: str | None = typer.Option(None, help="ISO created_at window end"),
    limit: int | None = typer.Option(None, help="Maximum PR count"),
    seed: int | None = typer.Option(None, help="Seed used when sampling with --limit"),
    cutoff_policy: str = typer.Option("created_at", help="Cutoff policy"),
    strict: bool = typer.Option(
        True,
        "--strict/--no-strict",
        help="Fail when profile coverage is missing",
    ),
    allow_fetch_missing_artifacts: bool = typer.Option(
        False,
        help="Fetch missing pinned artifacts before building profiles",
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
    selected_prs = _sample_prs(
        repo=repo,
        data_dir=data_dir,
        pr_numbers=list(pr),
        start_at=_parse_dt_option(start_at, option="--start-at"),
        end_at=_parse_dt_option(end_at, option="--end-at"),
        limit=limit,
        seed=seed,
    )
    if not selected_prs:
        raise typer.BadParameter("no PRs selected")

    cutoffs = _resolve_pr_cutoffs(
        repo=repo,
        data_dir=data_dir,
        pr_numbers=selected_prs,
        cutoff_policy=cutoff_policy,
        cohort_payload=None,
        require_complete_from_cohort=False,
    )
    chosen_run_id = run_id or ("profile-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    writer = ArtifactWriter(repo=repo, data_dir=data_dir, run_id=chosen_run_id)
    built = 0

    with HistoryReader(repo_full_name=repo, data_dir=data_dir) as reader:
        for pr_number in selected_prs:
            snap = reader.pull_request_snapshot(number=pr_number, as_of=cutoffs[pr_number])
            if snap.base_sha is None:
                if strict:
                    raise typer.BadParameter(f"missing base_sha for {repo}#{pr_number}")
                continue

            if allow_fetch_missing_artifacts:
                missing = _missing_artifact_paths(
                    repo=repo,
                    data_dir=data_dir,
                    base_sha=snap.base_sha,
                    artifact_paths=list(artifact_path),
                )
                if missing:
                    fetch_pinned_repo_artifacts_sync(
                        repo_full_name=repo,
                        base_sha=snap.base_sha,
                        data_dir=data_dir,
                        paths=missing,
                    )

            result = build_repo_profile(
                repo=repo,
                pr_number=pr_number,
                cutoff=cutoffs[pr_number],
                base_sha=snap.base_sha,
                data_dir=data_dir,
                artifact_paths=list(artifact_path),
                critical_artifact_paths=list(critical_artifact_path),
            )

            coverage = result.qa_report.coverage
            if strict and (not coverage.codeowners_present or coverage.missing_critical_artifacts):
                raise typer.BadParameter(
                    f"profile coverage failed for {repo}#{pr_number}: "
                    f"codeowners_present={coverage.codeowners_present}, "
                    f"missing_critical={coverage.missing_critical_artifacts}"
                )

            p_profile = writer.write_repo_profile(pr_number=pr_number, profile=result.profile)
            p_qa = writer.write_repo_profile_qa(
                pr_number=pr_number, qa_report=result.qa_report
            )
            typer.echo(f"wrote {p_profile}")
            typer.echo(f"wrote {p_qa}")
            built += 1

    typer.echo(f"run_id {chosen_run_id}")
    typer.echo(f"built_profiles {built}")
