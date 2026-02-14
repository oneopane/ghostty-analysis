"""Stable external API for evaluation_harness.

External packages should import evaluation entrypoints from this module only.
Internal modules (for example ``evaluation_harness.runner``) are not part of
the public cross-package contract.
"""

from __future__ import annotations

from .config import EvalDefaults, EvalRunConfig
from .artifact_service import list_artifacts, show_artifact
from .compare_summary import build_compare_summary, write_compare_summary
from .run_id import compute_run_id
from .run_summary import build_run_summary, write_run_summary
from .runner import RepoProfileRunSettings, RunResult
from .service import explain, list_runs, run, show

__all__ = [
    "EvalDefaults",
    "EvalRunConfig",
    "RepoProfileRunSettings",
    "RunResult",
    "build_compare_summary",
    "write_compare_summary",
    "compute_run_id",
    "build_run_summary",
    "write_run_summary",
    "list_artifacts",
    "show_artifact",
    "explain",
    "list_runs",
    "run",
    "show",
]
