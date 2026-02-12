"""Stable external API for evaluation_harness.

External packages should import evaluation entrypoints from this module only.
Internal modules (for example ``evaluation_harness.runner``) are not part of
the public cross-package contract.
"""

from __future__ import annotations

from .config import EvalDefaults, EvalRunConfig
from .run_id import compute_run_id
from .runner import RepoProfileRunSettings, RunResult
from .service import explain, list_runs, run, show

__all__ = [
    "EvalDefaults",
    "EvalRunConfig",
    "RepoProfileRunSettings",
    "RunResult",
    "compute_run_id",
    "explain",
    "list_runs",
    "run",
    "show",
]
