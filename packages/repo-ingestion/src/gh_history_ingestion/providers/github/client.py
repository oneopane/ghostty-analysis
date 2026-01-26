from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping
from urllib.parse import parse_qs, urlparse

import httpx
from aiolimiter import AsyncLimiter
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

try:
    from githubkit import GitHub
    from githubkit.auth import TokenAuthStrategy
except Exception:  # pragma: no cover - fallback if dependency unavailable
    GitHub = None
    TokenAuthStrategy = None


class RetryableGitHubError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitHubResponse:
    data: Any
    headers: Mapping[str, str]
    status_code: int | None = None


@dataclass(frozen=True)
class PaginationGap:
    resource: str | None
    url: str | None
    page: int | None
    expected_page: int | None
    detail: str | None


RequestFunc = Callable[
    [str, str, dict | None, dict | None, str | None],
    Awaitable[GitHubResponse],
]


class GitHubRestClient:
    def __init__(
        self,
        token: str,
        base_url: str = "https://api.github.com",
        limiter: AsyncLimiter | None = None,
        request_func: RequestFunc | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._limiter = limiter or AsyncLimiter(8, 1)
        self._request_func = request_func
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._gh = None
        if request_func is None:
            if GitHub and TokenAuthStrategy and hasattr(GitHub, "arequest"):
                self._gh = GitHub(auth=TokenAuthStrategy(token))
            else:
                self._client = httpx.AsyncClient(
                    base_url=self.base_url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "User-Agent": "repo-ingestion",
                    },
                    timeout=timeout,
                )

    async def __aenter__(self) -> "GitHubRestClient":
        if self._client is None and self._gh is None and self._request_func is None:
            raise RuntimeError("GitHub client unavailable.")
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        headers: dict | None = None,
        full_url: str | None = None,
    ) -> GitHubResponse:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((httpx.HTTPError, RetryableGitHubError)),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
            stop=stop_after_attempt(5),
            reraise=True,
        ):
            with attempt:
                async with self._limiter:
                    return await self._request(method, path, params, headers, full_url)
        raise RuntimeError("GitHub request retries exhausted")

    async def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        headers: dict | None = None,
        full_url: str | None = None,
    ) -> GitHubResponse:
        if self._request_func is not None:
            return await self._request_func(method, path, params, headers, full_url)

        if self._gh is not None:
            response = await self._gh.arequest(
                method,
                full_url or path,
                params=params,
                headers=headers,
            )
            status_code = getattr(response, "status_code", None)
            if status_code and status_code >= 400:
                if status_code in {403, 429, 500, 502, 503, 504}:
                    raise RetryableGitHubError(f"GitHub retryable {status_code}")
                raise RuntimeError(f"GitHub API error {status_code}")
            data = _extract_response_data(response)
            if status_code == 304:
                data = None
            return GitHubResponse(
                data=data, headers=response.headers, status_code=status_code
            )

        if self._client is None:
            raise RuntimeError("HTTP client not initialized")
        response = await self._client.request(
            method, path, params=params, headers=headers
        )
        if response.status_code == 304:
            return GitHubResponse(data=None, headers=response.headers, status_code=304)
        if response.status_code in {403, 429, 500, 502, 503, 504}:
            raise RetryableGitHubError(f"GitHub retryable {response.status_code}")
        response.raise_for_status()
        return GitHubResponse(
            data=response.json(),
            headers=response.headers,
            status_code=response.status_code,
        )

    async def get_json(self, path: str, params: dict | None = None) -> Any:
        response = await self.request("GET", path, params=params)
        return response.data

    async def paginate(
        self,
        path: str,
        params: dict | None = None,
        *,
        headers: dict | None = None,
        on_gap: Callable[[PaginationGap], None] | None = None,
        on_response: Callable[[GitHubResponse], None] | None = None,
        resource: str | None = None,
        max_pages: int | None = None,
    ):
        next_path = path
        next_params = params or {}
        page = int(next_params.get("page", 1)) if next_params else 1
        pages_seen = 0
        while next_path:
            response = await self.request(
                "GET", next_path, params=next_params, headers=headers
            )
            if on_response is not None:
                on_response(response)
            data = response.data or []
            next_path, next_params = _next_page(response.headers)
            if on_gap and not data and next_path:
                on_gap(
                    PaginationGap(
                        resource=resource,
                        url=next_path,
                        page=page,
                        expected_page=page,
                        detail="empty page with next link",
                    )
                )
            for item in data:
                yield item
            if next_path and on_gap:
                next_page = _extract_page(next_params)
                expected = page + 1
                if next_page is not None and next_page != expected:
                    on_gap(
                        PaginationGap(
                            resource=resource,
                            url=next_path,
                            page=next_page,
                            expected_page=expected,
                            detail="non-sequential page",
                        )
                    )
            pages_seen += 1
            if max_pages is not None and pages_seen >= max_pages:
                break
            page = _extract_page(next_params) or (page + 1)

    async def paginate_conditional(
        self,
        path: str,
        params: dict | None = None,
        *,
        headers: dict | None = None,
        on_gap: Callable[[PaginationGap], None] | None = None,
        on_response: Callable[[GitHubResponse], None] | None = None,
        resource: str | None = None,
        max_pages: int | None = None,
    ):
        response = await self.request("GET", path, params=params, headers=headers)
        if on_response is not None:
            on_response(response)
        if response.status_code == 304:
            return
        data = response.data or []
        next_path, next_params = _next_page(response.headers)
        for item in data:
            yield item
        if next_path:
            async for item in self.paginate(
                next_path,
                params=next_params,
                on_gap=on_gap,
                on_response=on_response,
                resource=resource,
                max_pages=None if max_pages is None else max_pages - 1,
            ):
                yield item


def _extract_response_data(response: Any) -> Any:
    if hasattr(response, "parsed_data"):
        return response.parsed_data
    if hasattr(response, "json"):
        return response.json()
    return response


def _next_page(headers: Mapping[str, str]) -> tuple[str | None, dict | None]:
    link = headers.get("Link") or headers.get("link")
    if not link:
        return None, None
    for part in link.split(","):
        section = part.strip()
        if 'rel="next"' not in section:
            continue
        url = section.split(";")[0].strip().lstrip("<").rstrip(">")
        parsed = urlparse(url)
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        return parsed.path, params
    return None, None


def _extract_page(params: dict | None) -> int | None:
    if not params:
        return None
    page_val = params.get("page")
    if page_val is None:
        return None
    try:
        return int(page_val)
    except (TypeError, ValueError):
        return None
