"""Demo: reusable analysis UI component (export + eval).

Run:
  uv run marimo edit notebooks/_components_demo_repo_analysis.py
  uv run marimo run notebooks/_components_demo_repo_analysis.py
"""

from __future__ import annotations

import marimo as mo

from repo_cli.marimo_components import repo_analysis_panel


app = mo.App(width="full")


@app.cell
def _(mo):
    mo.md("# Repo analysis component demo")
    return


@app.cell
def _():
    ui = repo_analysis_panel(default_repo="ghostty-org/ghostty", default_days_back=90)
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
