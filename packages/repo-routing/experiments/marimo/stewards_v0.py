from __future__ import annotations

import json
from pathlib import Path

import marimo as mo
import pyarrow.parquet as pq


app = mo.App()


@app.cell
def _():
    repo = mo.ui.text(label="repo", value="owner/name")
    export_run_id = mo.ui.text(label="export run id", value="run")
    data_dir = mo.ui.text(label="data dir", value="data")
    return repo, export_run_id, data_dir


@app.cell
def _(repo, export_run_id, data_dir):
    owner, name = repo.value.split("/", 1)
    export_dir = Path(data_dir.value) / "exports" / owner / name / export_run_id.value
    export_dir
    return export_dir, owner, name


@app.cell
def _(export_dir):
    def load_table(name: str):
        path = export_dir / name
        if not path.exists():
            return None
        return pq.read_table(path)

    prs = load_table("prs.parquet")
    pr_files = load_table("pr_files.parquet")
    pr_activity = load_table("pr_activity.parquet")
    return load_table, pr_activity, pr_files, prs


@app.cell
def _(mo, prs, pr_activity):
    if prs is None:
        mo.md("Missing `prs.parquet` in export dir.")
    else:
        mo.md(f"Loaded `{prs.num_rows}` PR rows.")

    if pr_activity is None:
        mo.md("Missing `pr_activity.parquet` in export dir.")
    else:
        mo.md(f"Loaded `{pr_activity.num_rows}` activity rows.")


@app.cell
def _(pr_activity):
    if pr_activity is None:
        return None
    try:
        df = pr_activity.to_pandas()
    except Exception:
        return None
    activity_counts = df.groupby("actor_login")["kind"].count().sort_values(ascending=False)
    activity_counts.head(10)


@app.cell
def _():
    def write_config(path: Path) -> Path:
        config = {
            "version": "v0",
            "feature_version": "v0",
            "candidate_pool": {
                "lookback_days": 180,
                "exclude_author": True,
                "exclude_bots": True,
            },
            "decay": {"half_life_days": 30, "lookback_days": 180},
            "event_weights": {
                "review_submitted": 1.0,
                "review_comment_created": 0.4,
                "comment_created": 0.2,
            },
            "weights": {"area_overlap_activity": 1.0, "activity_total": 0.2},
            "filters": {"min_activity_total": 0.0},
            "thresholds": {"confidence_high_margin": 0.15, "confidence_med_margin": 0.05},
            "labels": {"include_area_labels": False},
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
        return path

    write_config


if __name__ == "__main__":
    app.run()
