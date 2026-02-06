from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from repo_routing.history.models import PullRequestFile, PullRequestSnapshot
from repo_routing.inputs.models import PRInputBundle
from repo_routing.predictor.features.ownership import build_ownership_features


def _setup_files(tmp_path: Path, repo: str, base_sha: str) -> Path:
    owner, name = repo.split("/", 1)
    data_dir = tmp_path / "data"

    co = data_dir / "github" / owner / name / "codeowners" / base_sha / "CODEOWNERS"
    co.parent.mkdir(parents=True, exist_ok=True)
    co.write_text("src/* @alice\n*.md @docs-team\n", encoding="utf-8")

    area_overrides = data_dir / "github" / owner / name / "routing" / "area_overrides.json"
    area_overrides.parent.mkdir(parents=True, exist_ok=True)
    area_overrides.write_text(
        json.dumps({"src/*": "core"}, sort_keys=True),
        encoding="utf-8",
    )

    return data_dir


def _bundle(repo: str, base_sha: str) -> PRInputBundle:
    snap = PullRequestSnapshot(
        repo=repo,
        number=1,
        pull_request_id=10,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        base_sha=base_sha,
        changed_files=[
            PullRequestFile(path="src/app.py", status="modified", changes=5),
            PullRequestFile(path="README.md", status="modified", changes=1),
        ],
    )
    return PRInputBundle(
        repo=repo,
        pr_number=1,
        cutoff=datetime(2024, 1, 2, tzinfo=timezone.utc),
        snapshot=snap,
        changed_files=list(snap.changed_files),
        file_areas={"src/app.py": "core", "README.md": "__root__"},
    )


def test_build_ownership_features(tmp_path: Path) -> None:
    repo = "acme/widgets"
    base_sha = "deadbeef"
    data_dir = _setup_files(tmp_path, repo, base_sha)

    features = build_ownership_features(
        _bundle(repo, base_sha),
        data_dir=data_dir,
        active_candidates={"alice", "bob"},
    )

    assert features["pr.owners.owner_set_size"] >= 1
    assert features["pr.owners.coverage_ratio"] > 0.0
    assert features["pr.owners.zero_owner_found"] is False
    assert features["pr.owners.overlap_active_candidates"] >= 1
