"""Stable external API for repo_routing.

External packages should prefer importing from this module instead of deep
package internals when equivalent public accessors exist.
"""

from __future__ import annotations

from .history.reader import HistoryReader
from .registry import RouterSpec, load_router, router_id_for_spec
from .operators.registry import list_operator_ids
from .repo_profile.builder import build_repo_profile
from .repo_profile.storage import (
    CODEOWNERS_PATH_CANDIDATES,
    DEFAULT_PINNED_ARTIFACT_PATHS,
    pinned_artifact_path,
)
from .router_specs import build_router_specs
from .time import cutoff_key_utc, parse_dt_utc, require_dt_utc

__all__ = [
    "CODEOWNERS_PATH_CANDIDATES",
    "DEFAULT_PINNED_ARTIFACT_PATHS",
    "HistoryReader",
    "RouterSpec",
    "list_operator_ids",
    "build_repo_profile",
    "build_router_specs",
    "cutoff_key_utc",
    "load_router",
    "parse_dt_utc",
    "pinned_artifact_path",
    "require_dt_utc",
    "router_id_for_spec",
]
