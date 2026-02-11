from __future__ import annotations

import json
from datetime import timezone

import pytest
from evaluation_harness.config import EvalDefaults, EvalRunConfig
from evaluation_harness.runner import run_streaming_eval
from repo_routing.registry import RouterSpec

from .fixtures.build_min_db import build_min_db


def test_runner_strict_mode_fails_on_stale_cutoff(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)
    cfg = EvalRunConfig(
        repo=db.repo,
        data_dir=str(db.data_dir),
        run_id="run-stale-strict",
        defaults=EvalDefaults(
            strict_streaming_eval=True,
            cutoff_policy="created_at+60m",
        ),
    )

    with pytest.raises(RuntimeError, match="strict_streaming_eval violation"):
        run_streaming_eval(
            cfg=cfg,
            pr_numbers=[db.pr_number],
            router_specs=[RouterSpec(type="builtin", name="mentions")],
        )


def test_runner_non_strict_mode_records_stale_cutoff_note(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)
    cfg = EvalRunConfig(
        repo=db.repo,
        data_dir=str(db.data_dir),
        run_id="run-stale-nonstrict",
        defaults=EvalDefaults(
            strict_streaming_eval=False,
            cutoff_policy="created_at+60m",
        ),
    )

    result = run_streaming_eval(
        cfg=cfg,
        pr_numbers=[db.pr_number],
        router_specs=[RouterSpec(type="builtin", name="mentions")],
    )

    report = json.loads((result.run_dir / "report.json").read_text(encoding="utf-8"))
    notes = report.get("notes") or []
    assert any("db_max_event_occurred_at" in str(n) for n in notes)
    truth_counts = (report.get("extra") or {}).get("truth_coverage_counts") or {}
    assert isinstance(truth_counts, dict)


def test_runner_uses_provided_pr_cutoffs(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)
    cfg = EvalRunConfig(
        repo=db.repo,
        data_dir=str(db.data_dir),
        run_id="run-provided-cutoff",
        defaults=EvalDefaults(
            strict_streaming_eval=False,
            cutoff_policy="created_at+60m",
        ),
    )

    locked_cutoff = db.created_at.astimezone(timezone.utc)
    result = run_streaming_eval(
        cfg=cfg,
        pr_numbers=[db.pr_number],
        router_specs=[RouterSpec(type="builtin", name="mentions")],
        pr_cutoffs={db.pr_number: locked_cutoff},
    )

    row = json.loads((result.run_dir / "per_pr.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert row["cutoff"] == locked_cutoff.isoformat()

    manifest = json.loads((result.run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["cutoff_source"] == "provided"
    assert manifest["pr_cutoffs"][str(db.pr_number)] == locked_cutoff.isoformat()


def test_runner_rejects_incomplete_pr_cutoff_map(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)
    cfg = EvalRunConfig(repo=db.repo, data_dir=str(db.data_dir), run_id="run-missing-cutoff")

    with pytest.raises(ValueError, match="pr_cutoffs missing entries"):
        run_streaming_eval(
            cfg=cfg,
            pr_numbers=[db.pr_number],
            router_specs=[RouterSpec(type="builtin", name="mentions")],
            pr_cutoffs={},
        )
