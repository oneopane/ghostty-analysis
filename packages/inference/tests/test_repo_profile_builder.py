from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from repo_routing.repo_profile.builder import build_repo_profile


def _seed_artifacts(tmp_path: Path, *, repo: str, base_sha: str) -> Path:
    owner, name = repo.split("/", 1)
    data_dir = tmp_path / "data"
    base = data_dir / "github" / owner / name / "repo_artifacts" / base_sha
    (base / ".github").mkdir(parents=True, exist_ok=True)
    (base / ".github" / "CODEOWNERS").write_text(
        "src/* @alice @acme/reviewers\n*.md @docs-team\n",
        encoding="utf-8",
    )
    (base / "CONTRIBUTING.md").write_text(
        "Please link issue and include AI disclosure + provenance details.\n",
        encoding="utf-8",
    )
    return data_dir


def _stable_json_bytes(obj: object) -> bytes:
    return (
        json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        .encode("utf-8")
    )


def test_repo_profile_builder_is_deterministic(tmp_path: Path) -> None:
    repo = "acme/widgets"
    base_sha = "deadbeef"
    data_dir = _seed_artifacts(tmp_path, repo=repo, base_sha=base_sha)

    one = build_repo_profile(
        repo=repo,
        pr_number=7,
        cutoff=datetime(2024, 1, 1, tzinfo=timezone.utc),
        base_sha=base_sha,
        data_dir=data_dir,
    )
    two = build_repo_profile(
        repo=repo,
        pr_number=7,
        cutoff=datetime(2024, 1, 1, tzinfo=timezone.utc),
        base_sha=base_sha,
        data_dir=data_dir,
    )

    assert _stable_json_bytes(one.model_dump(mode="json")) == _stable_json_bytes(
        two.model_dump(mode="json")
    )
    assert one.qa_report.coverage.codeowners_present is True
    assert one.profile.ownership_graph.nodes
    assert one.profile.ownership_graph.edges
