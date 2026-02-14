from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from repo_routing.registry import RouterSpec
from repo_routing.repo_profile.storage import DEFAULT_PINNED_ARTIFACT_PATHS

from .config import EvalRunConfig
from .reporting.models import EvalReport
from .store.filesystem import FilesystemStore
from .truth_policy import ResolvedTruthPolicy
from sdlc_core.store import FileArtifactStore, FileRunStore


@dataclass(frozen=True)
class RunResult:
    run_dir: Path


@dataclass(frozen=True)
class RepoProfileRunSettings:
    strict: bool = True
    artifact_paths: tuple[str, ...] = DEFAULT_PINNED_ARTIFACT_PATHS
    critical_artifact_paths: tuple[str, ...] = ()


@dataclass
class PreparedEvalStage:
    cfg: EvalRunConfig
    specs: list[RouterSpec]
    router_ids: list[str]
    routers_by_id: dict[str, object]
    package_versions: dict[str, str | None]
    generated_at: datetime
    run_dir: Path
    store: FilesystemStore
    artifact_store: FileArtifactStore
    run_store: FileRunStore
    db_max_event_occurred_at: datetime | None
    db_max_watermark_updated_at: datetime | None
    cutoffs: dict[int, datetime]
    cutoff_source: str
    ordered_pr_numbers: list[int]
    stale_cutoff_note: str | None
    truth_window_seconds: int
    truth_policies: dict[str, ResolvedTruthPolicy]
    truth_primary_policy: str


@dataclass
class PerPrEvalStage:
    routing_rows_by_router: dict[str, list[object]]
    routing_rows_known_by_router: dict[str, list[object]]
    routing_rows_by_policy_router: dict[
        str, dict[str, list[tuple[object, object, bool]]]
    ]
    queue_rows_by_router: dict[str, list[object]]
    gate_rows: list[object]
    router_feature_meta: dict[str, dict[str, object]]
    truth_status_counts: dict[str, int]
    truth_status_counts_by_policy: dict[str, dict[str, int]]


@dataclass
class AggregatedEvalStage:
    routing_summaries: dict[str, object]
    routing_summaries_known: dict[str, object]
    routing_summaries_by_policy: dict[str, dict[str, object]]
    routing_denominators_by_policy: dict[str, dict[str, dict[str, int]]]
    routing_slices_by_policy: dict[str, dict[str, dict[str, dict[str, object]]]]
    gates_summary: object
    queue_summaries: dict[str, object]
    llm_telemetry: dict[str, object]
    notes: list[str]
    report: EvalReport
    truth_manifest: dict[str, object]
