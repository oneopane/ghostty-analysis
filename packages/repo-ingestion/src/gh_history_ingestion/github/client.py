"""Backwards compatible GitHub client.

New code should prefer `gh_history_ingestion.providers.github.client`.
"""

from ..providers.github.client import GitHubResponse, GitHubRestClient, PaginationGap

__all__ = ["GitHubRestClient", "GitHubResponse", "PaginationGap"]
