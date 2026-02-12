from __future__ import annotations

import typer
from gh_history_ingestion.cli.app import app as ingestion_app
from experimentation.unified_experiment import cohort_app, doctor, experiment_app, profile_app

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)
app.add_typer(ingestion_app, name="ingestion")
app.add_typer(cohort_app, name="cohort")
app.add_typer(experiment_app, name="experiment")
app.add_typer(profile_app, name="profile")
app.command("doctor")(doctor)


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
