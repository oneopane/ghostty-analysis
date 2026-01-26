"""Backwards compatible GitHub auth.

New code should prefer `gh_history_ingestion.providers.github.auth`.
"""

from ..providers.github.auth import select_auth_token

__all__ = ["select_auth_token"]
