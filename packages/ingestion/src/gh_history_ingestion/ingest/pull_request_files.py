from __future__ import annotations

from ..providers.github.client import GitHubRestClient
from ..storage.upsert import upsert_pull_request_file
from .qa import GapRecorder


async def ingest_pull_request_files(
    session,
    client: GitHubRestClient,
    owner: str,
    name: str,
    *,
    repo_id: int,
    pull_request_number: int,
    pull_request_id: int,
    head_sha: str | None,
    max_pages: int | None = None,
) -> None:
    if not head_sha:
        return

    async for file in client.paginate(
        f"/repos/{owner}/{name}/pulls/{pull_request_number}/files",
        params={"per_page": 100},
        on_gap=GapRecorder(session, repo_id, "pull_request_files"),
        resource="pull_request_files",
        max_pages=max_pages,
    ):
        upsert_pull_request_file(
            session,
            repo_id,
            pull_request_id,
            head_sha=head_sha,
            file=file,
        )
