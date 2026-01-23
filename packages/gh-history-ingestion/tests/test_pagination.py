import pytest

from gh_history_ingestion.github.client import GitHubResponse, GitHubRestClient


@pytest.mark.asyncio
async def test_pagination_follows_link_headers():
    responses = [
        GitHubResponse(
            data=[{"id": 1}, {"id": 2}],
            headers={
                "Link": '<https://api.github.com/resource?page=2&per_page=2>; rel="next", '
                '<https://api.github.com/resource?page=2&per_page=2>; rel="last"'
            },
        ),
        GitHubResponse(
            data=[{"id": 3}],
            headers={},
        ),
    ]
    call_count = {"count": 0}

    async def fake_request(method, path, params=None, full_url=None):
        call_count["count"] += 1
        return responses[call_count["count"] - 1]

    client = GitHubRestClient(
        token="x",
        request_func=fake_request,
    )

    items = [item async for item in client.paginate("/resource", params={"per_page": 2})]
    assert items == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert call_count["count"] == 2
