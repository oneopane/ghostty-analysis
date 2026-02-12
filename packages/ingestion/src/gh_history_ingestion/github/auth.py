"""Backwards compatible GitHub auth.

New code should prefer `gh_history_ingestion.providers.github.auth`.
Deprecated on 2026-02-12; planned removal after 2026-04-30.
"""

from ..providers.github.auth import select_auth_token

__all__ = ["select_auth_token"]
