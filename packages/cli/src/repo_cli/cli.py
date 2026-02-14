from __future__ import annotations

import json

import typer
from gh_history_ingestion.cli.app import app as ingestion_app
from experimentation.unified_experiment import cohort_app, doctor, experiment_app, profile_app
from repo_routing.runtime_defaults import DEFAULT_DATA_DIR

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)
artifacts_app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)
backfill_app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)
app.add_typer(ingestion_app, name="ingestion")
app.add_typer(cohort_app, name="cohort")
app.add_typer(experiment_app, name="experiment")
app.add_typer(profile_app, name="profile")
app.command("doctor")(doctor)
app.add_typer(artifacts_app, name="artifacts")
app.add_typer(backfill_app, name="backfill")


def _add_degraded_group(*, group_name: str, package_name: str, exc: Exception) -> None:
    reason = f"{exc.__class__.__name__}: {exc}"
    degraded = typer.Typer(
        add_completion=False,
        pretty_exceptions_show_locals=False,
        help=(
            f"Unavailable: failed to load optional package {package_name!r}. "
            f"Reason: {reason}"
        ),
    )

    @degraded.callback(invoke_without_command=True)
    def _degraded_callback() -> None:
        typer.secho(
            (
                f"degraded mode: `{group_name}` commands are unavailable because "
                f"package {package_name!r} failed to load ({reason})."
            ),
            fg=typer.colors.YELLOW,
            err=True,
        )
        raise typer.Exit(code=1)

    app.add_typer(degraded, name=group_name)


@artifacts_app.command("list")
def artifacts_list(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    run_id: str = typer.Option(..., "--run-id", help="Evaluation run id"),
    data_dir: str = typer.Option(DEFAULT_DATA_DIR, help="Base directory for per-repo data"),
) -> None:
    from evaluation_harness.api import list_artifacts as list_eval_artifacts

    rows = list_eval_artifacts(repo=repo, run_id=run_id, data_dir=data_dir)
    for row in rows:
        typer.echo(json.dumps(row, sort_keys=True, ensure_ascii=True))


@artifacts_app.command("show")
def artifacts_show(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    run_id: str = typer.Option(..., "--run-id", help="Evaluation run id"),
    artifact_id: str = typer.Option(..., "--artifact-id", help="Artifact id"),
    data_dir: str = typer.Option(DEFAULT_DATA_DIR, help="Base directory for per-repo data"),
) -> None:
    from evaluation_harness.api import show_artifact as show_eval_artifact

    try:
        payload = show_eval_artifact(
            repo=repo,
            run_id=run_id,
            artifact_id=artifact_id,
            data_dir=data_dir,
        )
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"artifact not found: {exc}") from exc
    typer.echo(json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2))


@backfill_app.command("semantic")
def backfill_semantic(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    prompt: str = typer.Option(..., "--prompt", help="Prompt id"),
    since: str = typer.Option(..., help="ISO timestamp lower bound"),
    data_dir: str = typer.Option(DEFAULT_DATA_DIR, help="Base directory for per-repo data"),
    dry_run: bool = typer.Option(False, help="Plan only; do not write outputs"),
) -> None:
    from repo_routing.semantic.backfill import backfill_semantic_artifacts

    payload = backfill_semantic_artifacts(
        repo=repo,
        prompt_id=prompt,
        since=since,
        data_dir=data_dir,
        dry_run=dry_run,
    )
    typer.echo(json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2))


try:
    from repo_routing.cli.app import app as routing_app

    app.add_typer(routing_app, name="inference")
except Exception as exc:
    _add_degraded_group(group_name="inference", package_name="inference", exc=exc)

try:
    from evaluation_harness.cli.app import app as eval_app

    app.add_typer(eval_app, name="evaluation")
except Exception as exc:
    _add_degraded_group(group_name="evaluation", package_name="evaluation", exc=exc)
