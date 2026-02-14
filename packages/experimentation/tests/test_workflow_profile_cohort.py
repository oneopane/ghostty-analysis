from __future__ import annotations

import hashlib
import json
from pathlib import Path

import typer
from typer.testing import CliRunner

import experimentation.unified_experiment as unified_experiment
import experimentation.workflow_profile as workflow_profile


def _build_app() -> typer.Typer:
    app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)
    app.add_typer(unified_experiment.profile_app, name="profile")
    return app


def _stable_hash_payload(payload: dict[str, object]) -> str:
    clean = dict(payload)
    clean.pop("hash", None)
    data = json.dumps(clean, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _write_cohort(path: Path, *, repo: str, pr_numbers: list[int]) -> None:
    pr_cutoffs = {str(n): "2024-01-01T00:00:00Z" for n in pr_numbers}
    payload: dict[str, object] = {
        "kind": "cohort",
        "version": "v1",
        "repo": repo,
        "cutoff_policy": "created_at",
        "cutoff_policy_mode": "v1",
        "cutoff_policy_version": "v1",
        "cutoff_policy_reason": "test",
        "filters": {"start_at": None, "end_at": None, "limit": None, "seed": None},
        "pr_numbers": list(pr_numbers),
        "pr_cutoffs": pr_cutoffs,
    }
    payload["hash"] = _stable_hash_payload(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )


class _FakeSnapshot:
    def __init__(self, *, base_sha: str | None) -> None:
        self.base_sha = base_sha


class _FakeHistoryReader:
    def __init__(self, *, repo_full_name: str, data_dir: str) -> None:
        self.repo_full_name = repo_full_name
        self.data_dir = data_dir

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False

    def pull_request_snapshot(self, *, number: int, as_of):  # type: ignore[no-untyped-def]
        return _FakeSnapshot(base_sha="deadbeef")


class _FakeCoverage:
    def __init__(
        self,
        *,
        codeowners_present: bool,
        missing_critical_artifacts: list[str] | None = None,
    ) -> None:
        self.codeowners_present = codeowners_present
        self.missing_critical_artifacts = list(missing_critical_artifacts or [])

    def model_dump(self, *, mode: str):  # type: ignore[no-untyped-def]
        return {
            "artifact_count": 0,
            "codeowners_present": bool(self.codeowners_present),
            "critical_artifacts": [],
            "present_critical_artifacts": [],
            "missing_critical_artifacts": list(self.missing_critical_artifacts),
        }


class _FakeQA:
    def __init__(self, *, coverage: _FakeCoverage) -> None:
        self.coverage = coverage


class _FakeBuildResult:
    def __init__(self, *, coverage_ok: bool) -> None:
        self.profile = {"kind": "repo_profile"}
        self.qa_report = _FakeQA(coverage=_FakeCoverage(codeowners_present=coverage_ok))


class _FakeWriter:
    def __init__(self, *, repo: str, data_dir: str, run_id: str) -> None:
        owner, name = repo.split("/", 1)
        self.run_dir = Path(data_dir) / "github" / owner / name / "eval" / run_id

    def write_repo_profile(self, *, pr_number: int, profile):  # type: ignore[no-untyped-def]
        p = self.run_dir / "prs" / str(pr_number) / "repo_profile" / "profile.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{}\n", encoding="utf-8")
        return p

    def write_repo_profile_qa(self, *, pr_number: int, qa_report):  # type: ignore[no-untyped-def]
        p = self.run_dir / "prs" / str(pr_number) / "repo_profile" / "qa.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{}\n", encoding="utf-8")
        return p


def test_profile_build_accepts_cohort_and_writes_summary(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    repo = "acme/widgets"
    data_dir = tmp_path / "data"
    cohort_path = tmp_path / "cohort.json"
    _write_cohort(cohort_path, repo=repo, pr_numbers=[1, 2])

    monkeypatch.setattr(workflow_profile, "HistoryReader", _FakeHistoryReader)
    monkeypatch.setattr(workflow_profile, "ArtifactWriter", _FakeWriter)
    monkeypatch.setattr(
        workflow_profile,
        "build_repo_profile",
        lambda **kwargs: _FakeBuildResult(coverage_ok=True),
    )

    runner = CliRunner()
    res = runner.invoke(
        _build_app(),
        [
            "profile",
            "build",
            "--repo",
            repo,
            "--data-dir",
            str(data_dir),
            "--cohort",
            str(cohort_path),
            "--run-id",
            "profile-test",
            "--no-strict",
        ],
    )
    assert res.exit_code == 0, res.output

    summary_path = None
    for line in res.output.splitlines():
        if line.startswith("profile_build_summary "):
            summary_path = line.split(" ", 1)[1].strip()
            break
    assert summary_path is not None
    p = Path(summary_path)
    assert p.exists()


def test_profile_build_strict_exits_nonzero_but_writes_summary(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    repo = "acme/widgets"
    data_dir = tmp_path / "data"
    cohort_path = tmp_path / "cohort.json"
    _write_cohort(cohort_path, repo=repo, pr_numbers=[1])

    monkeypatch.setattr(workflow_profile, "HistoryReader", _FakeHistoryReader)
    monkeypatch.setattr(workflow_profile, "ArtifactWriter", _FakeWriter)
    monkeypatch.setattr(
        workflow_profile,
        "build_repo_profile",
        lambda **kwargs: _FakeBuildResult(coverage_ok=False),
    )

    runner = CliRunner()
    res = runner.invoke(
        _build_app(),
        [
            "profile",
            "build",
            "--repo",
            repo,
            "--data-dir",
            str(data_dir),
            "--cohort",
            str(cohort_path),
            "--run-id",
            "profile-strict",
        ],
    )
    assert res.exit_code == 1

    summary_path = None
    for line in res.output.splitlines():
        if line.startswith("profile_build_summary "):
            summary_path = line.split(" ", 1)[1].strip()
            break
    assert summary_path is not None
    assert Path(summary_path).exists()
