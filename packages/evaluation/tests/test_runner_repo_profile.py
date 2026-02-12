from __future__ import annotations

import json

import pytest
from evaluation_harness.config import EvalRunConfig
from evaluation_harness.runner import RepoProfileRunSettings, run_streaming_eval
from repo_routing.registry import RouterSpec, router_id_for_spec

from .fixtures.build_min_db import build_min_db


def _seed_codeowners(db) -> None:  # type: ignore[no-untyped-def]
    owner, name = db.repo.split("/", 1)
    base = (
        db.data_dir
        / "github"
        / owner
        / name
        / "repo_artifacts"
        / ("deadbeef" * 5)
        / ".github"
    )
    base.mkdir(parents=True, exist_ok=True)
    (base / "CODEOWNERS").write_text("src/* @bob\n", encoding="utf-8")


def test_runner_writes_repo_profile_artifacts_and_per_pr_summary(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)
    _seed_codeowners(db)
    cfg = EvalRunConfig(repo=db.repo, data_dir=str(db.data_dir), run_id="run-profile")

    res = run_streaming_eval(
        cfg=cfg,
        pr_numbers=[db.pr_number],
        router_specs=[RouterSpec(type="builtin", name="mentions")],
        repo_profile_settings=RepoProfileRunSettings(strict=True),
    )

    pr_dir = res.run_dir / "prs" / str(db.pr_number)
    assert (pr_dir / "repo_profile" / "profile.json").exists()
    assert (pr_dir / "repo_profile" / "qa.json").exists()

    row = json.loads((res.run_dir / "per_pr.jsonl").read_text(encoding="utf-8").splitlines()[0])
    profile = row.get("repo_profile") or {}
    assert profile.get("status") in {"ok", "degraded"}
    coverage = profile.get("coverage") or {}
    assert coverage.get("codeowners_present") is True
    assert isinstance(row.get("truth_status"), str)
    assert isinstance(row.get("truth_diagnostics"), dict)


def test_runner_repo_profile_strict_fails_when_codeowners_missing(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)
    cfg = EvalRunConfig(repo=db.repo, data_dir=str(db.data_dir), run_id="run-profile-strict")

    with pytest.raises(RuntimeError, match="repo profile strict failure"):
        run_streaming_eval(
            cfg=cfg,
            pr_numbers=[db.pr_number],
            router_specs=[RouterSpec(type="builtin", name="mentions")],
            repo_profile_settings=RepoProfileRunSettings(strict=True),
        )


def test_runner_passes_repo_profile_context_into_router_bundle(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)
    _seed_codeowners(db)
    cfg = EvalRunConfig(repo=db.repo, data_dir=str(db.data_dir), run_id="run-profile-bundle")

    spec = RouterSpec(
        type="import_path",
        name="example-llm",
        import_path="repo_routing.examples.llm_router_example:create_router",
    )
    rid = router_id_for_spec(spec)

    res = run_streaming_eval(
        cfg=cfg,
        pr_numbers=[db.pr_number],
        router_specs=[spec],
        repo_profile_settings=RepoProfileRunSettings(strict=True),
    )

    expected_profile_path = (
        res.run_dir / "prs" / str(db.pr_number) / "repo_profile" / "profile.json"
    )
    features_path = res.run_dir / "prs" / str(db.pr_number) / "features" / f"{rid}.json"
    features = json.loads(features_path.read_text(encoding="utf-8"))

    assert features["repo_profile_path"] == str(expected_profile_path)
    assert features["repo_profile_codeowners_present"] is True
