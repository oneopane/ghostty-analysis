"""Reusable marimo UI components for this workspace.

This module is intended to be imported from marimo notebooks, e.g.

    from repo_cli.marimo_components import repo_ingestion_panel

    ui = repo_ingestion_panel(default_repo="ghostty-org/ghostty")
    ui["view"]
    # When buttons are clicked, ui["logs"].value updates.

Design goals:
- Keep notebooks thin: put CLI/UI glue here.
- Avoid hard dependency on marimo for non-notebook usage.
"""

from __future__ import annotations

import datetime as dt
import os
import shlex
import subprocess
import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict


@dataclass(frozen=True)
class CmdResult:
    cmd: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_s: float


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _to_rfc3339_z(ts: dt.datetime) -> str:
    ts = ts.astimezone(dt.timezone.utc).replace(microsecond=0)
    return ts.isoformat().replace("+00:00", "Z")


def _fmt_cmd(cmd: list[str]) -> str:
    return " ".join(shlex.quote(c) for c in cmd)


def _run_cmd(cmd: list[str], cwd: str | None = None) -> CmdResult:
    start = _utc_now()
    p = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )
    end = _utc_now()
    return CmdResult(
        cmd=cmd,
        returncode=int(p.returncode),
        stdout=p.stdout or "",
        stderr=p.stderr or "",
        duration_s=(end - start).total_seconds(),
    )


class IngestionPanel(TypedDict):
    view: Any
    values: dict[str, Any]
    db_path: Path
    start_at: str
    end_at: str
    cmds: dict[str, list[str]]
    logs: Any


class AnalysisPanel(TypedDict):
    view: Any
    values: dict[str, Any]
    export_dir: Path
    cmds: dict[str, list[str]]
    logs: Any


def repo_ingestion_panel(
    *,
    default_repo: str,
    default_days_back: int = 90,
    default_data_dir: str = "data",
    default_db_filename: str = "history.sqlite",
) -> IngestionPanel:
    """Create a reusable UI panel for `repo ingest` / `repo incremental` / `repo pull-requests`.

    Returns a dict with:
    - `view`: renderable marimo element
    - `values`: current form values
    - `db_path`: resolved per-repo sqlite path
    - `start_at` / `end_at`: RFC3339 timestamps
    - `cmds`: commands to run
    - `logs`: marimo state holding recent command runs
    """
    mo = importlib.import_module("marimo")  # type: ignore[assignment]

    repo = mo.ui.text(value=default_repo, label="Repo (owner/name)")
    days_back = mo.ui.slider(
        1, 365, value=default_days_back, step=1, label="Lookback (days)"
    )
    data_dir = mo.ui.text(value=default_data_dir, label="Data dir")
    db_name = mo.ui.text(value=default_db_filename, label="DB filename")
    max_pages = mo.ui.number(value=None, label="Dev max pages (optional)")

    mode = mo.ui.dropdown(
        options=["ingest", "incremental", "pull-requests"],
        value="ingest",
        label="Mode",
    )
    with_truth = mo.ui.checkbox(value=True, label="With truth (pull-requests)")

    form = mo.ui.form(
        mo.vstack(
            [
                mo.hstack([repo, days_back, mode]),
                mo.hstack([data_dir, db_name, max_pages]),
                mo.hstack([with_truth]),
            ]
        ),
        submit_button_label="Update",
        show_clear_button=False,
    )

    run_selected = mo.ui.button(label="Run selected")
    run_ingest = mo.ui.button(label="Run ingest")
    run_incremental = mo.ui.button(label="Run incremental")
    run_prs = mo.ui.button(label="Run pull-requests")
    buttons = mo.hstack([run_selected, run_ingest, run_incremental, run_prs])

    now = _utc_now()
    start_at = _to_rfc3339_z(
        now - dt.timedelta(days=int(form.value["Lookback (days)"]))
    )
    end_at = _to_rfc3339_z(now)

    repo_s = str(form.value["Repo (owner/name)"]).strip()
    if "/" not in repo_s:
        owner, name = "", repo_s
    else:
        owner, name = repo_s.split("/", 1)

    base = Path(str(form.value["Data dir"]).strip() or "data").expanduser()
    db_path = base / "github" / owner / name / str(form.value["DB filename"]).strip()

    ingest_cmd = [
        "uv",
        "run",
        "repo",
        "ingest",
        "--repo",
        repo_s,
        "--data-dir",
        str(base),
        "--db",
        str(db_path),
        "--start-at",
        start_at,
        "--end-at",
        end_at,
    ]
    if form.value["Dev max pages (optional)"] is not None:
        ingest_cmd.extend(
            ["--max-pages", str(int(form.value["Dev max pages (optional)"]))]
        )

    incremental_cmd = [
        "uv",
        "run",
        "repo",
        "incremental",
        "--repo",
        repo_s,
        "--data-dir",
        str(base),
        "--db",
        str(db_path),
    ]

    prs_cmd = [
        "uv",
        "run",
        "repo",
        "pull-requests",
        "--repo",
        repo_s,
        "--data-dir",
        str(base),
        "--db",
        str(db_path),
        "--start-at",
        start_at,
        "--end-at",
        end_at,
    ]
    if bool(form.value["With truth (pull-requests)"]):
        prs_cmd.append("--with-truth")

    cmds = {
        "ingest": ingest_cmd,
        "incremental": incremental_cmd,
        "pull-requests": prs_cmd,
    }

    logs = mo.state([])

    def append(res: CmdResult) -> None:
        logs.set(
            logs.value
            + [
                {
                    "cmd": _fmt_cmd(res.cmd),
                    "returncode": res.returncode,
                    "duration_s": res.duration_s,
                    "stdout": res.stdout,
                    "stderr": res.stderr,
                }
            ]
        )

    def maybe_run(which: str) -> None:
        res = _run_cmd(cmds[which])
        append(res)

    selected_mode = str(form.value["Mode"]).strip()
    if run_selected.value:
        maybe_run(selected_mode)
    if run_ingest.value:
        maybe_run("ingest")
    if run_incremental.value:
        maybe_run("incremental")
    if run_prs.value:
        maybe_run("pull-requests")

    view = mo.vstack(
        [
            mo.md("### Repo ingestion"),
            form,
            buttons,
            mo.md(f"Window: `{start_at}` -> `{end_at}`"),
            mo.md(f"DB: `{db_path}`"),
            mo.md(
                f"Selected: `{selected_mode}`  |  Cmd: `{_fmt_cmd(cmds[selected_mode])}`"
            ),
        ]
    )

    return {
        "view": view,
        "values": dict(form.value),
        "db_path": db_path,
        "start_at": start_at,
        "end_at": end_at,
        "cmds": cmds,
        "logs": logs,
    }


def repo_analysis_panel(
    *,
    default_repo: str,
    default_days_back: int = 90,
    default_data_dir: str = "data",
    default_export_config: str = "packages/repo-routing/experiments/configs/v0.json",
) -> AnalysisPanel:
    """Create a reusable UI panel for export (Parquet) + evaluation.

    This panel shells out to:
    - `packages/repo-routing/experiments/extract/export_v0.py`
    - `repo eval run`
    """

    mo = importlib.import_module("marimo")  # type: ignore[assignment]
    pc = importlib.import_module("pyarrow.compute")  # type: ignore[assignment]
    pq = importlib.import_module("pyarrow.parquet")  # type: ignore[assignment]

    repo = mo.ui.text(value=default_repo, label="Repo (owner/name)")
    days_back = mo.ui.slider(
        1, 365, value=default_days_back, step=1, label="Lookback (days)"
    )
    data_dir = mo.ui.text(value=default_data_dir, label="Data dir")

    # export options
    export_run_id = mo.ui.text(
        value=_to_rfc3339_z(_utc_now()).replace(":", "").replace("-", ""),
        label="Export run id",
    )
    include_text = mo.ui.checkbox(value=False, label="Include PR text")
    include_truth = mo.ui.checkbox(value=True, label="Include truth")

    # eval options
    router = mo.ui.dropdown(
        options=["mentions", "popularity", "stewards"],
        value="mentions",
        label="Router/baseline",
    )
    limit_prs = mo.ui.slider(10, 2000, value=200, step=10, label="Eval PR limit")
    config_path = mo.ui.text(
        value=default_export_config, label="Router config (stewards only)"
    )

    form = mo.ui.form(
        mo.vstack(
            [
                mo.hstack([repo, days_back, data_dir]),
                mo.hstack([export_run_id, include_text, include_truth]),
                mo.hstack([router, limit_prs, config_path]),
            ]
        ),
        submit_button_label="Update",
        show_clear_button=False,
    )

    run_export = mo.ui.button(label="Run export")
    run_eval = mo.ui.button(label="Run eval")
    run_both = mo.ui.button(label="Run export + eval")
    buttons = mo.hstack([run_export, run_eval, run_both])

    now = _utc_now()
    start_at = _to_rfc3339_z(
        now - dt.timedelta(days=int(form.value["Lookback (days)"]))
    )
    end_at = _to_rfc3339_z(now)

    repo_s = str(form.value["Repo (owner/name)"]).strip()
    owner, name = repo_s.split("/", 1)
    base = Path(str(form.value["Data dir"]).strip() or "data").expanduser()
    export_id = str(form.value["Export run id"]).strip()
    export_dir = base / "exports" / owner / name / export_id

    export_cmd = [
        "uv",
        "run",
        "--project",
        "packages/repo-routing",
        "python",
        "packages/repo-routing/experiments/extract/export_v0.py",
        "--repo",
        repo_s,
        "--export-run-id",
        export_id,
        "--from",
        start_at,
        "--end-at",
        end_at,
        "--data-dir",
        str(base),
    ]
    if bool(form.value["Include PR text"]):
        export_cmd.append("--include-text")
    if bool(form.value["Include truth"]):
        export_cmd.append("--include-truth")

    eval_cmd = [
        "uv",
        "run",
        "repo",
        "eval",
        "run",
        "--repo",
        repo_s,
        "--data-dir",
        str(base),
        "--from",
        start_at,
        "--end-at",
        end_at,
        "--baseline",
        str(form.value["Router/baseline"]),
        "--limit",
        str(int(form.value["Eval PR limit"])),
    ]
    if str(form.value["Router/baseline"]) == "stewards":
        eval_cmd.extend(["--config", str(form.value["Router config (stewards only)"])])

    cmds = {"export": export_cmd, "eval": eval_cmd}
    logs = mo.state([])

    def append(res: CmdResult) -> None:
        logs.set(
            logs.value
            + [
                {
                    "cmd": _fmt_cmd(res.cmd),
                    "returncode": res.returncode,
                    "duration_s": res.duration_s,
                    "stdout": res.stdout,
                    "stderr": res.stderr,
                }
            ]
        )

    def maybe_run(which: str) -> None:
        res = _run_cmd(cmds[which])
        append(res)

    if run_export.value or run_both.value:
        maybe_run("export")
    if run_eval.value or run_both.value:
        maybe_run("eval")

    # Lightweight Parquet preview (optional)
    activity_path = export_dir / "pr_activity.parquet"
    activity_counts: list[dict[str, Any]] | None = None
    if activity_path.exists():
        table = pq.read_table(activity_path)
        if "kind" in table.column_names:
            vc = pc.value_counts(table["kind"]).sort_by([("counts", "descending")])
            activity_counts = vc.to_pylist()

    view = mo.vstack(
        [
            mo.md("### Repo analysis (export + eval)"),
            form,
            buttons,
            mo.md(f"Window: `{start_at}` -> `{end_at}`"),
            mo.md(f"Export dir: `{export_dir}`"),
            mo.md(f"Export cmd: `{_fmt_cmd(export_cmd)}`"),
            mo.md(f"Eval cmd: `{_fmt_cmd(eval_cmd)}`"),
            mo.md("#### Activity kind counts (from pr_activity.parquet)"),
            mo.ui.table(activity_counts)
            if activity_counts is not None
            else mo.md("(run export first)"),
        ]
    )

    return {
        "view": view,
        "values": dict(form.value),
        "export_dir": export_dir,
        "cmds": cmds,
        "logs": logs,
    }
