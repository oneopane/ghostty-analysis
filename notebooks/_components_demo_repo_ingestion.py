"""Demo: reusable ingestion UI component.

Run:
  uv run marimo edit notebooks/_components_demo_repo_ingestion.py
  uv run marimo run notebooks/_components_demo_repo_ingestion.py
"""

from __future__ import annotations

import marimo as mo

from experimentation.marimo_components import repo_ingestion_panel


app = mo.App(width="full")


@app.cell
def _(mo):
    mo.md("# Repo ingestion component demo")
    return


@app.cell
def _():
    ui = repo_ingestion_panel(default_repo="ghostty-org/ghostty", default_days_back=90)
    ui["view"]
    return ui


@app.cell
def _(mo, ui):
    mo.md("## Recent runs")
    if not ui["logs"].value:
        mo.md("No runs yet.")
    else:
        mo.ui.table(list(reversed(ui["logs"].value))[:20])
    return


if __name__ == "__main__":
    app.run()
