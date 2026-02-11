from __future__ import annotations

import pytest

from gh_history_ingestion.repo_artifacts.fetcher import fetch_pinned_repo_artifacts


class _FakeClient:
    async def get_json(self, path, params=None):  # type: ignore[no-untyped-def]
        if path.endswith("/contents/.github/CODEOWNERS"):
            return {
                "encoding": "base64",
                "content": "c3JjLyogQGFsaWNlDQo=",  # "src/* @alice\r\n"
                "sha": "blob-sha-123",
                "url": "https://api.github.test/repos/acme/widgets/contents/.github/CODEOWNERS",
                "git_url": "https://api.github.test/repos/acme/widgets/git/blobs/blob-sha-123",
                "download_url": "https://raw.github.test/acme/widgets/abc123/.github/CODEOWNERS",
            }
        raise RuntimeError("GitHub API error 404")


@pytest.mark.asyncio
async def test_fetch_pinned_repo_artifacts_writes_manifest_and_files(tmp_path):
    manifest = await fetch_pinned_repo_artifacts(
        repo_full_name="acme/widgets",
        base_sha="abc123",
        data_dir=tmp_path / "data",
        paths=(".github/CODEOWNERS", "CONTRIBUTING.md"),
        client=_FakeClient(),  # type: ignore[arg-type]
    )

    assert [f.path for f in manifest.files] == [".github/CODEOWNERS"]
    assert manifest.files[0].blob_sha == "blob-sha-123"
    assert manifest.files[0].source_url is not None
    assert manifest.files[0].git_url is not None
    assert manifest.files[0].download_url is not None
    assert manifest.missing == ["CONTRIBUTING.md"]

    out = (
        tmp_path
        / "data"
        / "github"
        / "acme"
        / "widgets"
        / "repo_artifacts"
        / "abc123"
        / ".github"
        / "CODEOWNERS"
    )
    assert out.read_text(encoding="utf-8") == "src/* @alice\n"

    mp = (
        tmp_path
        / "data"
        / "github"
        / "acme"
        / "widgets"
        / "repo_artifacts"
        / "abc123"
        / "manifest.json"
    )
    assert mp.exists()
