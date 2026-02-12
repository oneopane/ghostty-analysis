from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import typer
import experimentation.unified_experiment as unified_experiment
import experimentation.workflow_eval as workflow_eval
import experimentation.workflow_run as workflow_run
from typer.testing import CliRunner


def _build_app() -> typer.Typer:
    app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)
    app.add_typer(unified_experiment.cohort_app, name="cohort")
    app.add_typer(unified_experiment.experiment_app, name="experiment")
    app.add_typer(unified_experiment.profile_app, name="profile")
    app.command("doctor")(unified_experiment.doctor)
    return app


def _seed_sampling_db(base_dir: Path, *, repo: str = "acme/widgets") -> Path:
    owner, name = repo.split("/", 1)
    db_path = base_dir / "github" / owner / name / "history.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("create table repos (id integer primary key, full_name text not null)")
        conn.execute(
            """
            create table pull_requests (
                id integer primary key,
                repo_id integer,
                number integer,
                created_at text
            )
            """
        )
        conn.execute("insert into repos (id, full_name) values (1, ?)", (repo,))
        conn.execute(
            "insert into pull_requests (id, repo_id, number, created_at) values (101, 1, 1, '2024-01-01 00:00:00')"
        )
        conn.execute(
            "insert into pull_requests (id, repo_id, number, created_at) values (102, 1, 2, '2024-01-02 00:00:00')"
        )
        conn.execute(
            "insert into pull_requests (id, repo_id, number, created_at) values (103, 1, 3, '2024-01-03 00:00:00')"
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


def _seed_run(
    *,
    data_dir: Path,
    repo: str,
    run_id: str,
    cohort_hash: str,
) -> None:
    owner, name = repo.split("/", 1)
    run_dir = data_dir / "github" / owner / name / "eval" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "report.json").write_text(
        json.dumps(
            {
                "routing_agreement": {
                    "mentions": {
                        "hit_at_1": 0.1,
                        "hit_at_3": 0.2,
                        "hit_at_5": 0.3,
                        "mrr": 0.4,
                    }
                }
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "per_pr.jsonl").write_text(
        json.dumps({"pr_number": 1}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_dir / "experiment_manifest.json").write_text(
        json.dumps(
            {
                "kind": "experiment_manifest",
                "version": "v1",
                "repo": repo,
                "run_id": run_id,
                "cohort_hash": cohort_hash,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_hashed_payload(path: Path, payload: dict[str, object]) -> dict[str, object]:
    payload = dict(payload)
    payload["hash"] = unified_experiment._stable_hash_payload(payload)  # type: ignore[attr-defined]
    path.write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def _cohort_payload(
    *,
    repo: str,
    pr_number: int,
    cutoff_iso: str,
) -> dict[str, object]:
    return {
        "kind": "cohort",
        "version": "v1",
        "repo": repo,
        "cutoff_policy": "created_at",
        "filters": {
            "start_at": None,
            "end_at": None,
            "limit": None,
            "seed": None,
        },
        "pr_numbers": [pr_number],
        "pr_cutoffs": {str(pr_number): cutoff_iso},
    }


def _spec_payload(
    *,
    repo: str,
    cohort_path: str | None,
    cohort_hash: str | None,
    allow_fetch_missing_artifacts: bool = False,
) -> dict[str, object]:
    return {
        "kind": "experiment_spec",
        "version": "v1",
        "repo": repo,
        "cohort": {
            "path": cohort_path,
            "hash": cohort_hash,
        },
        "cutoff_policy": "created_at",
        "strict_streaming_eval": True,
        "top_k": 5,
        "routers": [{"type": "builtin", "name": "mentions"}],
        "repo_profile": {
            "enabled": True,
            "strict": True,
            "allow_fetch_missing_artifacts": allow_fetch_missing_artifacts,
            "artifact_paths": [".github/CODEOWNERS"],
            "critical_artifact_paths": [],
        },
        "feature_policy_mode": "v0",
        "tags": [],
        "notes": "",
    }


def test_cohort_create_is_deterministic(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    _seed_sampling_db(data_dir)
    runner = CliRunner()

    out1 = tmp_path / "cohort1.json"
    out2 = tmp_path / "cohort2.json"

    args = [
        "cohort",
        "create",
        "--repo",
        "acme/widgets",
        "--data-dir",
        str(data_dir),
        "--limit",
        "2",
        "--seed",
        "42",
    ]
    r1 = runner.invoke(_build_app(), [*args, "--output", str(out1)])
    r2 = runner.invoke(_build_app(), [*args, "--output", str(out2)])

    assert r1.exit_code == 0, r1.output
    assert r2.exit_code == 0, r2.output

    c1 = json.loads(out1.read_text(encoding="utf-8"))
    c2 = json.loads(out2.read_text(encoding="utf-8"))
    assert c1["hash"] == c2["hash"]
    assert c1["pr_numbers"] == c2["pr_numbers"]


def test_experiment_diff_requires_matching_cohort_hash_unless_force(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    repo = "acme/widgets"
    _seed_run(data_dir=data_dir, repo=repo, run_id="run-a", cohort_hash="hash-a")
    _seed_run(data_dir=data_dir, repo=repo, run_id="run-b", cohort_hash="hash-b")

    runner = CliRunner()
    args = [
        "experiment",
        "diff",
        "--repo",
        repo,
        "--run-a",
        "run-a",
        "--run-b",
        "run-b",
        "--data-dir",
        str(data_dir),
    ]

    blocked = runner.invoke(_build_app(), args)
    assert blocked.exit_code != 0
    assert "cohort hash mismatch" in blocked.output

    forced = runner.invoke(_build_app(), [*args, "--force"])
    assert forced.exit_code == 0, forced.output


def test_experiment_run_uses_spec_locked_cohort_and_cutoffs(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    repo = "acme/widgets"
    data_dir = tmp_path / "data"
    run_dir = tmp_path / "run-output"
    cohort_path = tmp_path / "cohort.json"
    spec_path = tmp_path / "experiment.json"

    cohort = _write_hashed_payload(
        cohort_path,
        _cohort_payload(repo=repo, pr_number=17, cutoff_iso="2024-01-01T00:00:00Z"),
    )
    spec = _write_hashed_payload(
        spec_path,
        _spec_payload(
            repo=repo,
            cohort_path=str(cohort_path),
            cohort_hash=str(cohort["hash"]),
            allow_fetch_missing_artifacts=False,
        ),
    )

    captured: dict[str, object] = {}

    def _fake_run_streaming_eval(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        run_dir.mkdir(parents=True, exist_ok=True)
        return SimpleNamespace(run_dir=run_dir)

    monkeypatch.setattr(workflow_run, "run_eval", _fake_run_streaming_eval)
    monkeypatch.setattr(workflow_run, "compute_run_id", lambda cfg: "run-fixed")

    runner = CliRunner()
    res = runner.invoke(
        _build_app(),
        [
            "experiment",
            "run",
            "--spec",
            str(spec_path),
            "--data-dir",
            str(data_dir),
        ],
    )

    assert res.exit_code == 0, res.output
    assert captured["pr_numbers"] == [17]
    locked_cutoffs = captured["pr_cutoffs"]
    assert isinstance(locked_cutoffs, dict)
    assert locked_cutoffs[17] == datetime(2024, 1, 1, tzinfo=timezone.utc)

    manifest = json.loads((run_dir / "experiment_manifest.json").read_text(encoding="utf-8"))
    assert manifest["cohort_hash"] == cohort["hash"]
    assert manifest["experiment_spec_hash"] == spec["hash"]
    assert manifest["cutoff_source"] == "cohort_pr_cutoffs"
    assert manifest["pr_cutoffs"]["17"] == "2024-01-01T00:00:00Z"
    assert manifest["artifact_prefetch"]["network_used"] is False


def test_experiment_run_rejects_inline_cohort_flags_with_locked_spec_cohort(
    tmp_path: Path,
) -> None:
    repo = "acme/widgets"
    cohort_path = tmp_path / "cohort.json"
    spec_path = tmp_path / "experiment.json"

    cohort = _write_hashed_payload(
        cohort_path,
        _cohort_payload(repo=repo, pr_number=5, cutoff_iso="2024-01-01T00:00:00Z"),
    )
    _write_hashed_payload(
        spec_path,
        _spec_payload(
            repo=repo,
            cohort_path=str(cohort_path),
            cohort_hash=str(cohort["hash"]),
        ),
    )

    runner = CliRunner()
    res = runner.invoke(
        _build_app(),
        [
            "experiment",
            "run",
            "--spec",
            str(spec_path),
            "--from",
            "2024-01-01T00:00:00Z",
        ],
    )

    assert res.exit_code != 0
    assert "locks cohort" in res.output
    assert "cohort flags are not allowed" in res.output


def test_experiment_run_requires_cohort_path_for_hash_locked_spec(tmp_path: Path) -> None:
    repo = "acme/widgets"
    spec_path = tmp_path / "experiment.json"

    _write_hashed_payload(
        spec_path,
        _spec_payload(
            repo=repo,
            cohort_path=None,
            cohort_hash="deadbeef",
        ),
    )

    runner = CliRunner()
    res = runner.invoke(
        _build_app(),
        [
            "experiment",
            "run",
            "--spec",
            str(spec_path),
        ],
    )

    assert res.exit_code != 0
    assert "locks cohort by hash" in res.output


def test_experiment_run_records_prefetch_network_provenance_in_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    repo = "acme/widgets"
    data_dir = tmp_path / "data"
    run_dir = tmp_path / "run-prefetch"
    cohort_path = tmp_path / "cohort.json"
    spec_path = tmp_path / "experiment.json"

    cohort = _write_hashed_payload(
        cohort_path,
        _cohort_payload(repo=repo, pr_number=23, cutoff_iso="2024-01-02T00:00:00Z"),
    )
    _write_hashed_payload(
        spec_path,
        _spec_payload(
            repo=repo,
            cohort_path=str(cohort_path),
            cohort_hash=str(cohort["hash"]),
            allow_fetch_missing_artifacts=True,
        ),
    )

    prefetch_summary = {
        "enabled": True,
        "network_used": True,
        "requested_artifact_paths": [".github/CODEOWNERS"],
        "events": [
            {
                "repo": repo,
                "base_sha": "deadbeef",
                "trigger_pr_number": 23,
                "requested_paths": [".github/CODEOWNERS"],
                "source": {
                    "provider": "github_contents_api",
                    "repo": repo,
                    "ref": "deadbeef",
                    "endpoint_template": "/repos/{owner}/{repo}/contents/{path}?ref={ref}",
                },
                "manifest_path": str(
                    data_dir
                    / "github"
                    / "acme"
                    / "widgets"
                    / "repo_artifacts"
                    / "deadbeef"
                    / "manifest.json"
                ),
                "fetched_at": "2024-01-01T00:00:00+00:00",
                "fetched_files": [
                    {
                        "path": ".github/CODEOWNERS",
                        "content_sha256": "abc",
                        "size_bytes": 10,
                        "detected_type": "codeowners",
                        "blob_sha": "sha",
                        "source_url": "https://api.github.com/repos/acme/widgets/contents/.github/CODEOWNERS",
                        "git_url": "https://api.github.com/repos/acme/widgets/git/blobs/sha",
                        "download_url": "https://raw.githubusercontent.com/acme/widgets/deadbeef/.github/CODEOWNERS",
                    }
                ],
                "missing_after_fetch": [],
            }
        ],
    }

    monkeypatch.setattr(workflow_run, "_prefetch_missing_artifacts", lambda **kwargs: prefetch_summary)
    monkeypatch.setattr(workflow_run, "compute_run_id", lambda cfg: "run-prefetch")
    monkeypatch.setattr(
        workflow_run,
        "run_eval",
        lambda **kwargs: SimpleNamespace(run_dir=run_dir),
    )

    runner = CliRunner()
    res = runner.invoke(
        _build_app(),
        [
            "experiment",
            "run",
            "--spec",
            str(spec_path),
            "--data-dir",
            str(data_dir),
        ],
    )

    assert res.exit_code == 0, res.output
    manifest = json.loads((run_dir / "experiment_manifest.json").read_text(encoding="utf-8"))
    assert manifest["artifact_prefetch"]["network_used"] is True
    assert manifest["artifact_prefetch"]["events"][0]["base_sha"] == "deadbeef"
    assert manifest["artifact_prefetch"]["events"][0]["fetched_files"][0]["content_sha256"] == "abc"


def test_experiment_explain_passes_policy_flag(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    captured: dict[str, object] = {}

    def _fake_explain(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)

    monkeypatch.setattr(workflow_eval, "eval_explain", _fake_explain)

    runner = CliRunner()
    res = runner.invoke(
        _build_app(),
        [
            "experiment",
            "explain",
            "--repo",
            "acme/widgets",
            "--run-id",
            "run-x",
            "--pr",
            "7",
            "--router",
            "mentions",
            "--policy",
            "first_response_v1",
        ],
    )

    assert res.exit_code == 0, res.output
    assert captured["policy"] == "first_response_v1"


def test_experiment_run_audit_profile_enforces_quality_gates(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    repo = "acme/widgets"
    data_dir = tmp_path / "data"
    run_dir = data_dir / "github" / "acme" / "widgets" / "eval" / "run-gates"
    cohort_path = tmp_path / "cohort.json"
    spec_path = tmp_path / "experiment.json"

    cohort = _write_hashed_payload(
        cohort_path,
        _cohort_payload(repo=repo, pr_number=99, cutoff_iso="2024-01-01T00:00:00Z"),
    )
    spec = _spec_payload(
        repo=repo,
        cohort_path=str(cohort_path),
        cohort_hash=str(cohort["hash"]),
        allow_fetch_missing_artifacts=False,
    )
    spec["profile"] = "audit"
    _write_hashed_payload(spec_path, spec)

    def _fake_run_streaming_eval(**kwargs):  # type: ignore[no-untyped-def]
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "report.json").write_text(
            json.dumps(
                {
                    "kind": "eval_report",
                    "version": "v0",
                    "extra": {
                        "truth_coverage_counts": {
                            "observed": 0,
                            "unknown_due_to_ingestion_gap": 1,
                            "no_post_cutoff_response": 0,
                            "policy_unavailable": 0,
                        },
                        "truth_primary_policy": "first_approval_v1",
                    },
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        (run_dir / "per_pr.jsonl").write_text(
            json.dumps(
                {
                    "pr_number": 99,
                    "cutoff": "2024-01-01T00:00:00Z",
                    "truth_diagnostics": {
                        "window_end": "2024-01-01T01:00:00Z",
                    },
                    "repo_profile": {"coverage": {"codeowners_present": False}},
                    "routers": {
                        "mentions": {
                            "route_result": {"candidates": []},
                            "routing_agreement_by_policy": {
                                "first_approval_v1": {"mrr": 0.0, "hit_at_1": 0.0}
                            },
                        }
                    },
                    "truth": {
                        "primary_policy": "first_approval_v1",
                        "policies": {
                            "first_approval_v1": {
                                "status": "unknown_due_to_ingestion_gap",
                                "diagnostics": {},
                            }
                        },
                    },
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return SimpleNamespace(run_dir=run_dir)

    monkeypatch.setattr(workflow_run, "run_eval", _fake_run_streaming_eval)
    monkeypatch.setattr(workflow_run, "compute_run_id", lambda cfg: "run-gates")

    runner = CliRunner()
    res = runner.invoke(
        _build_app(),
        [
            "experiment",
            "run",
            "--spec",
            str(spec_path),
            "--data-dir",
            str(data_dir),
        ],
    )

    assert res.exit_code != 0
    assert "quality_gates_pass False" in res.output


def test_experiment_run_keeps_report_json_and_md_post_processing_in_sync(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    repo = "acme/widgets"
    data_dir = tmp_path / "data"
    run_dir = data_dir / "github" / "acme" / "widgets" / "eval" / "run-sync"
    cohort_path = tmp_path / "cohort.json"
    spec_path = tmp_path / "experiment.json"

    cohort = _write_hashed_payload(
        cohort_path,
        _cohort_payload(repo=repo, pr_number=41, cutoff_iso="2024-01-01T00:00:00Z"),
    )
    _write_hashed_payload(
        spec_path,
        _spec_payload(
            repo=repo,
            cohort_path=str(cohort_path),
            cohort_hash=str(cohort["hash"]),
            allow_fetch_missing_artifacts=False,
        ),
    )

    def _fake_run_streaming_eval(**kwargs):  # type: ignore[no-untyped-def]
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "report.json").write_text(
            json.dumps(
                {
                    "kind": "eval_report",
                    "version": "v0",
                    "routing_agreement": {"mentions": {"mrr": 0.5}},
                    "extra": {
                        "truth_coverage_counts": {
                            "observed": 1,
                            "unknown_due_to_ingestion_gap": 0,
                            "no_post_cutoff_response": 0,
                            "policy_unavailable": 0,
                        },
                        "truth_primary_policy": "first_approval_v1",
                    },
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        (run_dir / "report.md").write_text("# Evaluation Report\n\n- repo: acme/widgets\n", encoding="utf-8")
        (run_dir / "per_pr.jsonl").write_text(
            json.dumps(
                {
                    "pr_number": 41,
                    "cutoff": "2024-01-01T00:00:00Z",
                    "truth_diagnostics": {"window_end": "2024-01-01T01:00:00Z"},
                    "routers": {
                        "mentions": {
                            "route_result": {"candidates": [{"target": {"name": "alice"}, "score": 1.0}]},
                            "routing_agreement_by_policy": {
                                "first_approval_v1": {"mrr": 0.5, "hit_at_1": 1.0}
                            },
                        }
                    },
                    "truth": {
                        "primary_policy": "first_approval_v1",
                        "policies": {
                            "first_approval_v1": {
                                "status": "observed",
                                "diagnostics": {},
                            }
                        },
                    },
                    "repo_profile": {"coverage": {"codeowners_present": True}},
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return SimpleNamespace(run_dir=run_dir)

    monkeypatch.setattr(workflow_run, "run_eval", _fake_run_streaming_eval)
    monkeypatch.setattr(workflow_run, "compute_run_id", lambda cfg: "run-sync")

    runner = CliRunner()
    res = runner.invoke(
        _build_app(),
        [
            "experiment",
            "run",
            "--spec",
            str(spec_path),
            "--data-dir",
            str(data_dir),
        ],
    )
    assert res.exit_code == 0, res.output

    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")

    assert "quality_gates" in (report_json.get("extra") or {})
    assert "promotion_evaluation" in (report_json.get("extra") or {})
    assert "<!-- experiment-post-processing:start -->" in report_md
    assert "\"quality_gates\"" in report_md
    assert "\"promotion_evaluation\"" in report_md
