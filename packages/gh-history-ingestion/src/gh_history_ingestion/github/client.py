from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping
from urllib.parse import parse_qs, urlparse

import httpx
from aiolimiter import AsyncLimiter
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

try:
    from githubkit import GitHub
    from githubkit.auth import OAuthTokenAuthStrategy
except Exception:  # pragma: no cover - fallback if dependency unavailable
    GitHub = None
    OAuthTokenAuthStrategy = None


class RetryableGitHubError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitHubResponse:
    data: Any
    headers: Mapping[str, str]


RequestFunc = Callable[
    [str, str, dict | None, str | None],
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
            if GitHub and OAuthTokenAuthStrategy and hasattr(GitHub, "arequest"):
                self._gh = GitHub(auth=OAuthTokenAuthStrategy(token))
            else:
                self._client = httpx.AsyncClient(
                    base_url=self.base_url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "User-Agent": "gh-history-ingestion",
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
                    return await self._request(method, path, params, full_url)
        raise RuntimeError("GitHub request retries exhausted")

    async def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        full_url: str | None = None,
    ) -> GitHubResponse:
        if self._request_func is not None:
            return await self._request_func(method, path, params, full_url)

        if self._gh is not None:
            response = await self._gh.arequest(
                method,
                full_url or path,
                params=params,
            )
            status_code = getattr(response, "status_code", None)
            if status_code and status_code >= 400:
                if status_code in {403, 429, 500, 502, 503, 504}:
                    raise RetryableGitHubError(f"GitHub retryable {status_code}")
                raise RuntimeError(f"GitHub API error {status_code}")
            data = _extract_response_data(response)
            return GitHubResponse(data=data, headers=response.headers)

        if self._client is None:
            raise RuntimeError("HTTP client not initialized")
        response = await self._client.request(method, path, params=params)
        if response.status_code in {403, 429, 500, 502, 503, 504}:
            raise RetryableGitHubError(f"GitHub retryable {response.status_code}")
        response.raise_for_status()
        return GitHubResponse(data=response.json(), headers=response.headers)

    async def get_json(self, path: str, params: dict | None = None) -> Any:
        response = await self.request("GET", path, params=params)
        return response.data

    async def paginate(self, path: str, params: dict | None = None):
        next_path = path
        next_params = params or {}
        while next_path:
            response = await self.request("GET", next_path, params=next_params)
            data = response.data or []
            for item in data:
                yield item
            next_path, next_params = _next_page(response.headers)


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
