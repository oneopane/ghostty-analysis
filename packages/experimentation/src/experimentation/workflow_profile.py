from __future__ import annotations

from datetime import datetime, timezone

import typer
from gh_history_ingestion.repo_artifacts.fetcher import fetch_pinned_repo_artifacts_sync
from repo_routing.artifacts.writer import ArtifactWriter
from repo_routing.history.reader import HistoryReader
from repo_routing.repo_profile.builder import build_repo_profile

from .workflow_artifacts import _missing_artifact_paths
from .workflow_helpers import (
    DEFAULT_PINNED_ARTIFACT_PATHS,
    _parse_dt_option,
    _resolve_pr_cutoffs,
    _sample_prs,
)


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
