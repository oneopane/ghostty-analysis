import marimo

__generated_with = "0.19.7"
app = marimo.App(width="full")


@app.cell
def _():
    import csv
    import hashlib
    import json
    from datetime import datetime, timezone
    from pathlib import Path

    import marimo as mo

    return Path, csv, datetime, hashlib, json, mo, timezone


@app.cell
def _(mo):
    mo.md(
        """
        # Experiment audit notebook (Ghostty)

        Audit checklist for locked inputs, provenance, denominator-aware metrics, and sampled evidence.
        """
    )
    return


@app.cell
def _(mo):
    data_dir = mo.ui.text(value="data", label="data_dir")
    repo = mo.ui.text(value="ghostty-org/ghostty", label="repo")
    run_id = mo.ui.text(value="audit-ghostty-20260210-6mo-s4242-r3-v3", label="run_id")
    mo.hstack([data_dir, repo, run_id])
    return data_dir, repo, run_id


@app.cell
def _(Path, data_dir, repo, run_id):
    owner, name = repo.value.split("/", 1)
    run_dir = Path(data_dir.value) / "github" / owner / name / "eval" / run_id.value
    required = [
        "cohort.json",
        "experiment.json",
        "experiment_manifest.json",
        "manifest.json",
        "report.json",
        "per_pr.jsonl",
    ]
    missing = [f for f in required if not (run_dir / f).exists()]
    if missing:
        raise FileNotFoundError(f"Missing required files in {run_dir}: {missing}")
    return name, owner, required, run_dir


@app.cell
def _(json, run_dir):
    cohort = json.loads((run_dir / "cohort.json").read_text())
    experiment = json.loads((run_dir / "experiment.json").read_text())
    experiment_manifest = json.loads((run_dir / "experiment_manifest.json").read_text())
    manifest = json.loads((run_dir / "manifest.json").read_text())
    report = json.loads((run_dir / "report.json").read_text())

    rows = []
    with (run_dir / "per_pr.jsonl").open() as _f:
        for _line in _f:
            if _line.strip():
                rows.append(json.loads(_line))

    if any("truth_status" not in _r or "truth_diagnostics" not in _r for _r in rows):
        raise ValueError("per_pr rows missing truth fields")

    return cohort, experiment, experiment_manifest, manifest, report, rows


@app.cell
def _(cohort, experiment_manifest, manifest, mo):
    checks = {
        "cohort_hash": experiment_manifest.get("cohort_hash"),
        "spec_hash": experiment_manifest.get("experiment_spec_hash"),
        "cohort_pr_count": len(cohort.get("pr_numbers") or []),
        "cutoff_source_experiment_manifest": experiment_manifest.get("cutoff_source"),
        "cutoff_source_eval_manifest": manifest.get("cutoff_source"),
        "cutoff_lock_ok": (
            experiment_manifest.get("cutoff_source") == "cohort_pr_cutoffs"
            and manifest.get("cutoff_source") == "provided"
            and bool(experiment_manifest.get("pr_cutoffs"))
            and bool(manifest.get("pr_cutoffs"))
        ),
    }
    mo.md("## Locked inputs / cutoff lock")
    mo.ui.table([checks])
    return checks


@app.cell
def _(experiment_manifest, mo):
    prefetch = experiment_manifest.get("artifact_prefetch") or {}
    mo.md("## Provenance / network mode")
    mo.ui.table(
        [
            {
                "network_used": prefetch.get("network_used"),
                "enabled": prefetch.get("enabled"),
                "requested_artifact_paths": len(prefetch.get("requested_artifact_paths") or []),
                "events": len(prefetch.get("events") or []),
            }
        ]
    )
    return prefetch


@app.cell
def _(report):
    all_metrics = [
        {"router": _router, **(_vals or {})}
        for _router, _vals in (report.get("routing_agreement") or {}).items()
    ]
    known_metrics = [
        {"router": _router, **(_vals or {})}
        for _router, _vals in ((report.get("extra") or {}).get("routing_agreement_known_truth") or {}).items()
    ]
    truth_cov = [
        {"status": _k, "count": _v}
        for _k, _v in ((report.get("extra") or {}).get("truth_coverage_counts") or {}).items()
    ]
    return all_metrics, known_metrics, truth_cov


@app.cell
def _(all_metrics, known_metrics, mo):
    mo.md("## Metrics (all vs known-truth denominator)")
    mo.hstack([
        mo.vstack([mo.md("### All rows"), mo.ui.table(all_metrics)]),
        mo.vstack([mo.md("### Known truth"), mo.ui.table(known_metrics)]),
    ])
    return


@app.cell
def _(mo, truth_cov):
    mo.md(
        """
        ## Truth coverage interpretation
        - `observed`: eligible post-cutoff response found.
        - `no_post_cutoff_response`: no eligible response in truth window.
        - `unknown_due_to_ingestion_gap`: cannot determine due to ingestion horizon/gaps.
        """
    )
    mo.ui.table(truth_cov)
    return


@app.cell
def _(rows):
    audit_rows = []
    for _r in sorted(rows, key=lambda _x: int(_x["pr_number"])):
        _pop = ((_r.get("routers") or {}).get("popularity") or {})
        _rr = _pop.get("route_result") or {}
        _ag = _pop.get("routing_agreement") or {}
        _cands = _rr.get("candidates") or []
        _top1 = ((_cands[0].get("target") or {}).get("name")) if _cands else None
        audit_rows.append(
            {
                "pr_number": _r.get("pr_number"),
                "truth_status": _r.get("truth_status"),
                "truth_targets": len(_r.get("truth_behavior") or []),
                "top1_candidate": _top1,
                "hit@1": _ag.get("hit_at_1"),
                "hit@3": _ag.get("hit_at_3"),
                "hit@5": _ag.get("hit_at_5"),
                "repo_profile_status": (_r.get("repo_profile") or {}).get("status"),
                "gap_resources": ";".join((_r.get("truth_diagnostics") or {}).get("gap_resources") or []),
            }
        )
    return audit_rows


@app.cell
def _(audit_rows, mo):
    mo.md("## Per-PR audit table (popularity router view)")
    mo.ui.table(audit_rows)
    return


@app.cell
def _(rows):
    ordered = sorted(rows, key=lambda _r: int(_r["pr_number"]))

    correct = None
    for _r in ordered:
        if _r.get("truth_status") == "unknown_due_to_ingestion_gap":
            continue
        _ag = (((_r.get("routers") or {}).get("popularity") or {}).get("routing_agreement") or {})
        if float(_ag.get("hit_at_1", 0.0)) >= 1.0:
            correct = (_r, "hit@1")
            break
    if correct is None:
        for _r in ordered:
            if _r.get("truth_status") == "unknown_due_to_ingestion_gap":
                continue
            _ag = (((_r.get("routers") or {}).get("popularity") or {}).get("routing_agreement") or {})
            if float(_ag.get("hit_at_3", 0.0)) >= 1.0:
                correct = (_r, "hit@3")
                break

    incorrect = None
    for _r in ordered:
        if _r.get("truth_status") == "unknown_due_to_ingestion_gap":
            continue
        _ag = (((_r.get("routers") or {}).get("popularity") or {}).get("routing_agreement") or {})
        if float(_ag.get("hit_at_5", 0.0)) <= 0.0:
            incorrect = _r
            break

    if correct is None or incorrect is None:
        raise ValueError("Could not find deterministic correct/incorrect examples")

    return correct, incorrect


@app.cell
def _(correct, incorrect, mo):
    mo.md("## Deterministic examples")
    mo.ui.table(
        [
            {
                "type": "correct",
                "pr_number": correct[0].get("pr_number"),
                "rule": correct[1],
                "truth_status": correct[0].get("truth_status"),
                "truth_behavior": ", ".join(correct[0].get("truth_behavior") or []),
            },
            {
                "type": "incorrect",
                "pr_number": incorrect.get("pr_number"),
                "rule": "hit@5=0",
                "truth_status": incorrect.get("truth_status"),
                "truth_behavior": ", ".join(incorrect.get("truth_behavior") or []),
            },
        ]
    )
    return


@app.cell
def _(mo):
    mo.md("## Human sign-off checklist")
    signoff_checks = [
        mo.ui.checkbox(value=False, label="Locked inputs verified"),
        mo.ui.checkbox(value=False, label="Cutoff lock verified"),
        mo.ui.checkbox(value=False, label="Network mode understood"),
        mo.ui.checkbox(value=False, label="Truth coverage interpreted"),
        mo.ui.checkbox(value=False, label="Correct + incorrect examples reviewed"),
        mo.ui.checkbox(value=False, label="Denominator guidance acknowledged"),
    ]
    mo.vstack(signoff_checks)
    return signoff_checks


@app.cell
def _(Path, correct, csv, datetime, hashlib, incorrect, json, report, rows, run_dir, timezone):
    verification_dir = run_dir / "verification"
    examples_dir = verification_dir / "examples"
    verification_dir.mkdir(parents=True, exist_ok=True)
    examples_dir.mkdir(parents=True, exist_ok=True)

    def _sha(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as _f:
            for _chunk in iter(lambda: _f.read(1024 * 1024), b""):
                h.update(_chunk)
        return h.hexdigest()

    (verification_dir / "truth_coverage_breakdown.json").write_text(
        json.dumps(((report.get("extra") or {}).get("truth_coverage_counts") or {}), indent=2, sort_keys=True)
        + "\n"
    )

    metrics_summary = {
        "all_rows": report.get("routing_agreement") or {},
        "known_truth_rows": ((report.get("extra") or {}).get("routing_agreement_known_truth") or {}),
    }
    (verification_dir / "metrics_summary.json").write_text(
        json.dumps(metrics_summary, indent=2, sort_keys=True) + "\n"
    )

    sample = sorted(rows, key=lambda _x: int(_x["pr_number"]))[:25]
    with (verification_dir / "sampled_pr_evidence.csv").open("w", newline="") as _f:
        _w = csv.writer(_f)
        _w.writerow(["pr_number", "truth_status", "router_id", "hit_at_1", "hit_at_3", "hit_at_5"])
        for _r in sample:
            _ag = (((_r.get("routers") or {}).get("popularity") or {}).get("routing_agreement") or {})
            _w.writerow([
                _r.get("pr_number"),
                _r.get("truth_status"),
                "popularity",
                _ag.get("hit_at_1"),
                _ag.get("hit_at_3"),
                _ag.get("hit_at_5"),
            ])

    (examples_dir / "correct_example.json").write_text(json.dumps(correct[0], indent=2, sort_keys=True) + "\n")
    (examples_dir / "incorrect_example.json").write_text(json.dumps(incorrect, indent=2, sort_keys=True) + "\n")

    prov = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "report_sha256": _sha(run_dir / "report.json"),
        "manifest_sha256": _sha(run_dir / "manifest.json"),
        "per_pr_sha256": _sha(run_dir / "per_pr.jsonl"),
    }
    (verification_dir / "provenance_manifest.json").write_text(json.dumps(prov, indent=2, sort_keys=True) + "\n")

    return examples_dir, prov, sample, verification_dir


if __name__ == "__main__":
    app.run()
