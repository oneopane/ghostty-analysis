"""Backwards compatible imports.

New code should prefer `gh_history_ingestion.providers.github`.
"""

from ..providers.github.auth import select_auth_token
from ..providers.github.client import GitHubRestClient, GitHubResponse

__all__ = ["select_auth_token", "GitHubRestClient", "GitHubResponse"]
