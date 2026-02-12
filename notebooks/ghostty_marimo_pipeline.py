import marimo

__generated_with = "0.19.7"
app = marimo.App(width="full")


@app.cell
def _():
    """Bootstrap cell.

    marimo executes imports inside cells; return the shared modules/utilities
    that other cells depend on.
    """

    import datetime as dt
    import os
    import shlex
    import sqlite3
    import subprocess
    from dataclasses import dataclass
    from pathlib import Path
    from typing import Any

    import marimo as mo
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    @dataclass(frozen=True)
    class CmdResult:
        cmd: list[str]
        returncode: int
        stdout: str
        stderr: str
        duration_s: float

    def utc_now() -> dt.datetime:
        return dt.datetime.now(dt.timezone.utc)

    def to_rfc3339_z(ts: dt.datetime) -> str:
        ts = ts.astimezone(dt.timezone.utc).replace(microsecond=0)
        return ts.isoformat().replace("+00:00", "Z")

    def fmt_cmd(cmd: list[str]) -> str:
        return " ".join(shlex.quote(c) for c in cmd)

    def run_cmd(cmd: list[str]) -> CmdResult:
        start = utc_now()
        p = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            env=os.environ.copy(),
        )
        end = utc_now()
        return CmdResult(
            cmd=cmd,
            returncode=int(p.returncode),
            stdout=p.stdout or "",
            stderr=p.stderr or "",
            duration_s=(end - start).total_seconds(),
        )

    def read_db_stats(db_path: Path) -> dict[str, Any]:
        if not db_path.exists():
            return {"exists": False, "path": str(db_path)}

        con = sqlite3.connect(str(db_path))
        try:
            cur = con.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [r[0] for r in cur.fetchall()]
            out: dict[str, Any] = {
                "exists": True,
                "path": str(db_path),
                "tables": tables,
            }

            for t in (
                "pull_requests",
                "pull_request_reviews",
                "issue_comments",
                "issue_events",
            ):
                if t in tables:
                    cur.execute(f"SELECT COUNT(1) FROM {t}")
                    out[f"rows:{t}"] = int(cur.fetchone()[0])
            return out
        finally:
            con.close()

    def parquet_summary(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"exists": False, "path": str(path)}
        pf = pq.ParquetFile(path)
        schema = pf.schema_arrow
        return {
            "exists": True,
            "path": str(path),
            "rows": int(pf.metadata.num_rows) if pf.metadata is not None else None,
            "row_groups": int(pf.metadata.num_row_groups)
            if pf.metadata is not None
            else None,
            "cols": len(schema),
        }

    return (
        Any,
        CmdResult,
        Path,
        dt,
        fmt_cmd,
        mo,
        parquet_summary,
        pc,
        pq,
        read_db_stats,
        run_cmd,
        to_rfc3339_z,
        utc_now,
    )


@app.cell
def _(mo):
    mo.md(
        """
        # Ghostty pipeline

        GitHub -> `history.sqlite` -> Parquet exports -> evaluation.

        - Use the form to pick a repo and lookback window
        - Run ingest/export/eval via buttons
        - Inspect SQLite/Parquet sanity checks
        """
    )
    return


@app.cell
def _(mo, to_rfc3339_z, utc_now):
    repo = mo.ui.text(value="ghostty-org/ghostty", label="Repo (owner/name)")
    days_back = mo.ui.slider(7, 365, value=90, step=1, label="Lookback (days)")
    data_dir = mo.ui.text(value="data", label="Data dir")
    db_filename = mo.ui.text(value="history.sqlite", label="DB filename")
    max_pages = mo.ui.number(value=None, label="Dev max pages (optional)")

    limit_prs = mo.ui.slider(10, 2000, value=200, step=10, label="Eval PR limit")
    baseline = mo.ui.dropdown(
        options=["mentions", "popularity", "stewards"],
        value="mentions",
        label="Router/baseline",
    )
    stewards_config = mo.ui.text(
        value="experiments/configs/v0.json",
        label="Stewards config",
    )

    export_run_id = mo.ui.text(
        value=to_rfc3339_z(utc_now()).replace(":", "").replace("-", ""),
        label="Export run id",
    )
    include_text = mo.ui.checkbox(value=False, label="Export PR text")
    include_truth = mo.ui.checkbox(value=True, label="Export truth")

    controls = {
        "repo": repo,
        "days_back": days_back,
        "data_dir": data_dir,
        "db_filename": db_filename,
        "max_pages": max_pages,
        "limit_prs": limit_prs,
        "baseline": baseline,
        "stewards_config": stewards_config,
        "export_run_id": export_run_id,
        "include_text": include_text,
        "include_truth": include_truth,
    }

    mo.vstack(
        [
            mo.md("## Controls"),
            mo.hstack([repo, days_back, data_dir]),
            mo.hstack([db_filename, max_pages]),
            mo.hstack([baseline, limit_prs, stewards_config]),
            mo.hstack([export_run_id, include_text, include_truth]),
        ]
    )
    return controls


@app.cell
def _(dt, controls, to_rfc3339_z, utc_now):
    now = utc_now()
    start_at = now - dt.timedelta(days=int(controls["days_back"].value))
    start_at_s = to_rfc3339_z(start_at)
    end_at_s = to_rfc3339_z(now)
    return end_at_s, start_at_s


@app.cell
def _(Path, controls):
    repo_s = str(controls["repo"].value).strip()
    owner, name = repo_s.split("/", 1)
    base = Path(str(controls["data_dir"].value).strip() or "data").expanduser()
    db_path = (
        base / "github" / owner / name / str(controls["db_filename"].value).strip()
    )
    export_dir = (
        base / "exports" / owner / name / str(controls["export_run_id"].value).strip()
    )
    return base, db_path, export_dir, repo_s


@app.cell
def _(base, controls, db_path, end_at_s, repo_s, start_at_s):
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
        start_at_s,
        "--end-at",
        end_at_s,
    ]
    if controls["max_pages"].value is not None:
        ingest_cmd.extend(["--max-pages", str(int(controls["max_pages"].value))])

    export_cmd = [
        "uv",
        "run",
        "--project",
        "packages/inference",
        "python",
        "experiments/extract/export_v0.py",
        "--repo",
        repo_s,
        "--export-run-id",
        str(controls["export_run_id"].value).strip(),
        "--from",
        start_at_s,
        "--end-at",
        end_at_s,
        "--data-dir",
        str(base),
    ]
    if bool(controls["include_text"].value):
        export_cmd.append("--include-text")
    if bool(controls["include_truth"].value):
        export_cmd.append("--include-truth")

    eval_cmd = [
        "uv",
        "run",
        "repo",
        "evaluation",
        "run",
        "--repo",
        repo_s,
        "--data-dir",
        str(base),
        "--from",
        start_at_s,
        "--end-at",
        end_at_s,
        "--baseline",
        str(controls["baseline"].value),
        "--limit",
        str(int(controls["limit_prs"].value)),
    ]
    if str(controls["baseline"].value) == "stewards":
        eval_cmd.extend(["--config", str(controls["stewards_config"].value)])

    return eval_cmd, export_cmd, ingest_cmd


@app.cell
def _(eval_cmd, export_cmd, fmt_cmd, ingest_cmd, mo):
    mo.md("## Commands")
    mo.md(f"Ingest: `{fmt_cmd(ingest_cmd)}`")
    mo.md(f"Export: `{fmt_cmd(export_cmd)}`")
    mo.md(f"Eval: `{fmt_cmd(eval_cmd)}`")
    return


@app.cell
def _(mo):
    mo.md("## Run")
    run_ingest = mo.ui.button(label="Run ingest")
    run_export = mo.ui.button(label="Run export")
    run_eval = mo.ui.button(label="Run eval")
    run_all = mo.ui.button(label="Run ingest + export + eval")
    mo.hstack([run_ingest, run_export, run_eval, run_all])
    return run_all, run_eval, run_export, run_ingest


@app.cell
def _(
    CmdResult,
    eval_cmd,
    export_cmd,
    fmt_cmd,
    ingest_cmd,
    mo,
    run_all,
    run_cmd,
    run_eval,
    run_export,
    run_ingest,
):
    logs = mo.state([])

    def append(res: CmdResult) -> None:
        logs.set(
            logs.value
            + [
                {
                    "cmd": fmt_cmd(res.cmd),
                    "returncode": res.returncode,
                    "duration_s": res.duration_s,
                    "stdout": res.stdout,
                    "stderr": res.stderr,
                }
            ]
        )

    if run_ingest.value or run_all.value:
        append(run_cmd(ingest_cmd))
    if run_export.value or run_all.value:
        append(run_cmd(export_cmd))
    if run_eval.value or run_all.value:
        append(run_cmd(eval_cmd))

    mo.md("## Recent runs")
    if logs.value:
        mo.ui.table(list(reversed(logs.value))[:20])
    else:
        mo.md("No runs yet.")
    return logs


@app.cell
def _(db_path, mo, read_db_stats):
    mo.md("## SQLite sanity checks")
    stats = read_db_stats(db_path)
    if not stats.get("exists"):
        mo.callout(f"DB not found: {db_path}", kind="warning")
    else:
        mo.md(f"DB: `{db_path}`")
        mo.ui.table([{"key": k, "value": v} for k, v in stats.items() if k != "tables"])
        mo.md("Tables (first 200):")
        mo.ui.table([{"table": t} for t in stats.get("tables", [])[:200]])
    return


@app.cell
def _(Path, export_dir, mo, parquet_summary):
    mo.md("## Parquet exports")
    mo.md(f"Export dir: `{export_dir}`")
    files = [
        "prs.parquet",
        "prs_text.parquet",
        "pr_files.parquet",
        "pr_activity.parquet",
        "truth_behavior.parquet",
        "truth_intent.parquet",
        "export_manifest.json",
    ]
    rows = []
    for f in files:
        p = export_dir / f
        if f.endswith(".parquet"):
            s = parquet_summary(p)
            rows.append(
                {
                    "file": f,
                    "exists": s.get("exists"),
                    "rows": s.get("rows"),
                    "cols": s.get("cols"),
                }
            )
        else:
            rows.append({"file": f, "exists": p.exists(), "rows": None, "cols": None})
    mo.ui.table(rows)
    return export_dir / "pr_activity.parquet"


@app.cell
def _(activity_pq, mo, pc, pq):
    mo.md("## Activity snapshot")
    if not activity_pq.exists():
        mo.callout("No pr_activity.parquet yet; run export.", kind="info")
    else:
        table = pq.read_table(activity_pq)
        if "kind" in table.column_names:
            vc = pc.value_counts(table["kind"]).sort_by([("counts", "descending")])
            mo.ui.table(vc.to_pylist())
        else:
            mo.callout("Unexpected schema: missing 'kind' column", kind="warning")
    return


if __name__ == "__main__":
    app.run()
