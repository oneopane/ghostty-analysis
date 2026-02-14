from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
from gh_history_ingestion.repo_artifacts.fetcher import fetch_pinned_repo_artifacts_sync
from repo_routing.artifacts.writer import ArtifactWriter
from repo_routing.api import HistoryReader, build_repo_profile
from evaluation_harness.paths import repo_eval_run_dir

from .workflow_artifacts import _missing_artifact_paths
from .workflow_helpers import (
    DEFAULT_PINNED_ARTIFACT_PATHS,
    _parse_dt_option,
    _read_json,
    _resolve_pr_cutoffs,
    _sample_prs,
    _validate_hashed_payload,
    _write_json,
)


def profile_build(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    data_dir: str = typer.Option("data", help="Base directory for repo data"),
    run_id: str | None = typer.Option(None, help="Run id for profile artifacts"),
    cohort: str | None = typer.Option(None, help="Optional cohort JSON path"),
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
    cohort_payload: dict[str, Any] | None = None
    selected_prs: list[int]
    if cohort is not None:
        if (
            pr
            or start_at is not None
            or end_at is not None
            or limit is not None
            or seed is not None
        ):
            raise typer.BadParameter(
                "--cohort is mutually exclusive with --pr/--start-at/--end-at/--limit/--seed"
            )
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
            seed=seed,
        )

    if not selected_prs:
        raise typer.BadParameter("no PRs selected")

    cutoffs = _resolve_pr_cutoffs(
        repo=repo,
        data_dir=data_dir,
        pr_numbers=selected_prs,
        cutoff_policy=cutoff_policy,
        cohort_payload=cohort_payload,
        require_complete_from_cohort=True if cohort_payload is not None else False,
    )
    chosen_run_id = run_id or (
        "profile-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    writer = ArtifactWriter(repo=repo, data_dir=data_dir, run_id=chosen_run_id)
    run_dir = repo_eval_run_dir(
        repo_full_name=repo, data_dir=data_dir, run_id=chosen_run_id
    )

    built = 0
    skipped_missing_base_sha = 0
    failures: list[str] = []
    per_pr: list[dict[str, object]] = []
    fetched_base_shas: set[str] = set()
    fetched_path_count = 0

    with HistoryReader(repo_full_name=repo, data_dir=data_dir) as reader:
        for pr_number in selected_prs:
            snap = reader.pull_request_snapshot(
                number=pr_number, as_of=cutoffs[pr_number]
            )
            if snap.base_sha is None:
                skipped_missing_base_sha += 1
                per_pr.append(
                    {
                        "pr_number": int(pr_number),
                        "base_sha": None,
                        "status": "skipped_missing_base_sha",
                    }
                )
                if strict:
                    failures.append(f"missing base_sha for {repo}#{pr_number}")
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
                    fetched_base_shas.add(str(snap.base_sha))
                    fetched_path_count += int(len(missing))

            try:
                result = build_repo_profile(
                    repo=repo,
                    pr_number=pr_number,
                    cutoff=cutoffs[pr_number],
                    base_sha=snap.base_sha,
                    data_dir=data_dir,
                    artifact_paths=list(artifact_path),
                    critical_artifact_paths=list(critical_artifact_path),
                )
            except Exception as exc:
                failures.append(
                    f"build_repo_profile error for {repo}#{pr_number}: {exc}"
                )
                per_pr.append(
                    {
                        "pr_number": int(pr_number),
                        "base_sha": str(snap.base_sha),
                        "status": "error",
                        "error": str(exc),
                    }
                )
                continue

            coverage = result.qa_report.coverage
            coverage_failed = not bool(coverage.codeowners_present) or bool(
                coverage.missing_critical_artifacts
            )
            if strict and coverage_failed:
                failures.append(
                    f"profile coverage failed for {repo}#{pr_number}: "
                    f"codeowners_present={coverage.codeowners_present}, "
                    f"missing_critical={coverage.missing_critical_artifacts}"
                )

            p_profile = writer.write_repo_profile(
                pr_number=pr_number, profile=result.profile
            )
            p_qa = writer.write_repo_profile_qa(
                pr_number=pr_number, qa_report=result.qa_report
            )
            typer.echo(f"wrote {p_profile}")
            typer.echo(f"wrote {p_qa}")
            built += 1
            per_pr.append(
                {
                    "pr_number": int(pr_number),
                    "base_sha": str(snap.base_sha),
                    "status": "built" if not coverage_failed else "built_degraded",
                    "profile_path": str(p_profile),
                    "qa_path": str(p_qa),
                    "coverage": coverage.model_dump(mode="json"),
                }
            )

    def _pr_key(row: dict[str, object]) -> int:
        v = row.get("pr_number")
        if isinstance(v, int):
            return v
        try:
            return int(str(v))
        except Exception:
            return 0

    per_pr.sort(key=_pr_key)
    summary_path = run_dir / "profile_build_summary.json"
    _write_json(
        summary_path,
        {
            "schema_version": 1,
            "kind": "profile_build_summary",
            "generated_at": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "repo": repo,
            "run_id": chosen_run_id,
            "run_dir": str(run_dir),
            "data_dir": str(data_dir),
            "cohort": {
                "path": None if cohort is None else str(Path(cohort)),
                "hash": None
                if cohort_payload is None
                else (str(cohort_payload.get("hash") or "") or None),
            },
            "inputs": {
                "cutoff_policy": cutoff_policy,
                "strict": bool(strict),
                "allow_fetch_missing_artifacts": bool(allow_fetch_missing_artifacts),
                "artifact_paths": list(artifact_path),
                "critical_artifact_paths": list(critical_artifact_path),
            },
            "counts": {
                "selected_prs": int(len(selected_prs)),
                "built_profiles": int(built),
                "skipped_missing_base_sha": int(skipped_missing_base_sha),
                "failure_count": int(len(failures)),
                "fetched_base_sha_count": int(len(fetched_base_shas)),
                "fetched_path_count": int(fetched_path_count),
            },
            "failures": sorted(set(failures), key=lambda s: str(s).lower()),
            "per_pr": per_pr,
        },
    )

    typer.echo(f"run_id {chosen_run_id}")
    typer.echo(f"built_profiles {built}")
    typer.echo(f"profile_build_summary {summary_path}")
    if strict and failures:
        raise typer.Exit(code=1)
