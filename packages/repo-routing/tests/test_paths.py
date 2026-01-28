from pathlib import Path

from repo_routing.paths import repo_codeowners_dir, repo_codeowners_path, repo_db_path


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
