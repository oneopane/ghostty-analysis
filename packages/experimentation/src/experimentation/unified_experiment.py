from __future__ import annotations

from pathlib import Path

import typer
from evaluation_harness.api import compute_run_id
from evaluation_harness.api import explain as eval_explain_cmd
from evaluation_harness.api import list_runs as eval_list_runs_cmd
from evaluation_harness.api import run as run_streaming_eval
from evaluation_harness.api import show as eval_show_cmd
from repo_routing.runtime_defaults import DEFAULT_DATA_DIR

from .workflow_cohort import cohort_create
from .workflow_diff import experiment_diff
from .workflow_doctor import doctor
from .workflow_eval import experiment_explain, experiment_list, experiment_show
from .workflow_summaries import experiment_compare, experiment_summarize
from .workflow_promote import experiment_promote
from .workflow_index_all import experiment_index_all
from .workflow_artifacts import (
    _build_repo_profile_settings,
    _missing_artifact_paths,
    _prefetch_missing_artifacts,
)
from .workflow_helpers import (
    CODEOWNERS_PATH_CANDIDATES,
    DEFAULT_PINNED_ARTIFACT_PATHS,
    _build_cohort_payload,
    _build_router_specs,
    _inline_cohort_overrides,
    _iso_utc,
    _parse_dt_option,
    _read_json,
    _resolve_pr_cutoffs,
    _router_specs_from_spec,
    _sample_prs,
    _spec_cohort_ref,
    _spec_from_inline,
    _stable_hash_payload,
    _stable_json,
    _validate_hashed_payload,
    _write_json,
    pinned_artifact_path,
)
from .workflow_profile import profile_build
from .workflow_quality import (
    _quality_thresholds,
    evaluate_promotion,
    evaluate_quality_gates,
    persist_report_post_processing,
)
from .workflow_registry import CandidateRegistry
from workflow.reports import (
    EXPERIMENT_MANIFEST_FILENAME,
    _delta,
    _load_per_pr_rows,
    _load_report,
    _load_run_context,
    _run_context_payload,
)
from .workflow_run import experiment_run
from .workflow_spec import experiment_init


cohort_app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)
experiment_app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)
profile_app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)
candidate_app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)

cohort_app.command("create")(cohort_create)
experiment_app.command("init")(experiment_init)
experiment_app.command("run")(experiment_run)
experiment_app.command("show")(experiment_show)
experiment_app.command("list")(experiment_list)
experiment_app.command("explain")(experiment_explain)
experiment_app.command("diff")(experiment_diff)
experiment_app.command("summarize")(experiment_summarize)
experiment_app.command("compare")(experiment_compare)
experiment_app.command("promote")(experiment_promote)
experiment_app.command("index-all")(experiment_index_all)
experiment_app.add_typer(candidate_app, name="candidate")
profile_app.command("build")(profile_build)


@candidate_app.command("add")
def candidate_add(
    task_id: str = typer.Option(..., help="Task id"),
    candidate_ref: str = typer.Option(..., help="Candidate reference"),
    data_dir: str = typer.Option(DEFAULT_DATA_DIR, help="Base directory for repo data"),
) -> None:
    reg = CandidateRegistry(root=Path(data_dir))
    reg.register(task_id=task_id, candidate_ref=candidate_ref)
    typer.echo(f"candidate_added {task_id} {candidate_ref}")


@candidate_app.command("list")
def candidate_list(
    task_id: str = typer.Option(..., help="Task id"),
    data_dir: str = typer.Option(DEFAULT_DATA_DIR, help="Base directory for repo data"),
) -> None:
    reg = CandidateRegistry(root=Path(data_dir))
    typer.echo(reg.get(task_id=task_id))


@candidate_app.command("promote")
def candidate_promote(
    task_id: str = typer.Option(..., help="Task id"),
    candidate_ref: str = typer.Option(..., help="Candidate reference"),
    data_dir: str = typer.Option(DEFAULT_DATA_DIR, help="Base directory for repo data"),
) -> None:
    reg = CandidateRegistry(root=Path(data_dir))
    reg.promote(task_id=task_id, candidate_ref=candidate_ref)
    typer.echo(f"candidate_promoted {task_id} {candidate_ref}")
