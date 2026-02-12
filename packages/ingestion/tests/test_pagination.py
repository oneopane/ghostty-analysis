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

    async def fake_request(method, path, params=None, headers=None, full_url=None):
        call_count["count"] += 1
        return responses[call_count["count"] - 1]

    client = GitHubRestClient(
        token="x",
        request_func=fake_request,
    )

    items = [item async for item in client.paginate("/resource", params={"per_page": 2})]
    assert items == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert call_count["count"] == 2


@pytest.mark.asyncio
async def test_paginate_conditional_skips_on_304():
    call_count = {"count": 0}

    async def fake_request(method, path, params=None, headers=None, full_url=None):
        call_count["count"] += 1
        return GitHubResponse(data=None, headers={"ETag": '"abc"'}, status_code=304)

    client = GitHubRestClient(token="x", request_func=fake_request)

    items = [
        item
        async for item in client.paginate_conditional(
            "/resource", headers={"If-None-Match": '"abc"'}
        )
    ]
    assert items == []
    assert call_count["count"] == 1


@pytest.mark.asyncio
async def test_paginate_reports_gap_on_skipped_page():
    responses = [
        GitHubResponse(
            data=[{"id": 1}],
            headers={
                "Link": '<https://api.github.com/resource?page=3&per_page=1>; rel="next"'
            },
        ),
        GitHubResponse(
            data=[{"id": 2}],
            headers={},
        ),
    ]
    call_count = {"count": 0}

    async def fake_request(method, path, params=None, headers=None, full_url=None):
        call_count["count"] += 1
        return responses[call_count["count"] - 1]

    gaps = []

    def on_gap(info):
        gaps.append(info)

    client = GitHubRestClient(token="x", request_func=fake_request)
    items = [
        item
        async for item in client.paginate(
            "/resource", params={"per_page": 1, "page": 1}, on_gap=on_gap
        )
    ]
    assert items == [{"id": 1}, {"id": 2}]
    assert len(gaps) == 1
    assert gaps[0].expected_page == 2


@pytest.mark.asyncio
async def test_paginate_max_pages_limits_results():
    responses = [
        GitHubResponse(
            data=[{"id": 1}],
            headers={
                "Link": '<https://api.github.com/resource?page=2&per_page=1>; rel="next"'
            },
        ),
        GitHubResponse(
            data=[{"id": 2}],
            headers={
                "Link": '<https://api.github.com/resource?page=3&per_page=1>; rel="next"'
            },
        ),
    ]
    call_count = {"count": 0}

    async def fake_request(method, path, params=None, headers=None, full_url=None):
        call_count["count"] += 1
        return responses[call_count["count"] - 1]

    client = GitHubRestClient(token="x", request_func=fake_request)
    items = [
        item
        async for item in client.paginate(
            "/resource", params={"per_page": 1, "page": 1}, max_pages=1
        )
    ]
    assert items == [{"id": 1}]
    assert call_count["count"] == 1
