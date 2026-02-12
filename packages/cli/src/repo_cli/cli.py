from gh_history_ingestion.cli.app import app as app
from experimentation.unified_experiment import cohort_app, doctor, experiment_app, profile_app

app.add_typer(cohort_app, name="cohort")
app.add_typer(experiment_app, name="experiment")
app.add_typer(profile_app, name="profile")
app.command("doctor")(doctor)

try:
    from repo_routing.cli.app import app as routing_app

    app.add_typer(routing_app, name="inference")
except Exception:
    pass

try:
    from evaluation_harness.cli.app import app as eval_app

    app.add_typer(eval_app, name="evaluation")
except Exception:
    pass
