from gh_history_ingestion.cli.app import app as app

try:
    from repo_routing.cli.app import app as routing_app

    app.add_typer(routing_app, name="routing")
except Exception:
    pass

try:
    from evaluation_harness.cli.app import app as eval_app

    app.add_typer(eval_app, name="eval")
except Exception:
    pass
