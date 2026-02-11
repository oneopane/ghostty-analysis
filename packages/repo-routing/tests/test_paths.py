from pathlib import Path

from repo_routing.paths import (
    repo_artifact_base_dir,
    repo_artifact_path,
    repo_artifacts_dir,
    repo_codeowners_dir,
    repo_codeowners_path,
    repo_db_path,
)


def test_repo_paths() -> None:
    data_dir = Path("/tmp/data")
    repo = "octo-org/octo-repo"
    assert repo_db_path(repo_full_name=repo, data_dir=data_dir) == Path(
        "/tmp/data/github/octo-org/octo-repo/history.sqlite"
    )
    assert repo_codeowners_dir(repo_full_name=repo, data_dir=data_dir) == Path(
        "/tmp/data/github/octo-org/octo-repo/codeowners"
    )
    assert repo_codeowners_path(
        repo_full_name=repo, base_sha="abc", data_dir=data_dir
    ) == Path("/tmp/data/github/octo-org/octo-repo/codeowners/abc/CODEOWNERS")
    assert repo_artifacts_dir(repo_full_name=repo, data_dir=data_dir) == Path(
        "/tmp/data/github/octo-org/octo-repo/repo_artifacts"
    )
    assert repo_artifact_base_dir(
        repo_full_name=repo, base_sha="abc", data_dir=data_dir
    ) == Path("/tmp/data/github/octo-org/octo-repo/repo_artifacts/abc")
    assert repo_artifact_path(
        repo_full_name=repo,
        base_sha="abc",
        relative_path=".github/CODEOWNERS",
        data_dir=data_dir,
    ) == Path("/tmp/data/github/octo-org/octo-repo/repo_artifacts/abc/.github/CODEOWNERS")
