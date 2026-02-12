"""Backwards compatible GitHub client.

New code should prefer `gh_history_ingestion.providers.github.client`.
Deprecated on 2026-02-12; planned removal after 2026-04-30.
"""

from ..providers.github.client import GitHubResponse, GitHubRestClient, PaginationGap

__all__ = ["GitHubRestClient", "GitHubResponse", "PaginationGap"]
