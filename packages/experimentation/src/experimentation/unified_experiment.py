from __future__ import annotations

import typer
from evaluation_harness.run_id import compute_run_id
from evaluation_harness.service import explain as eval_explain_cmd
from evaluation_harness.service import list_runs as eval_list_runs_cmd
from evaluation_harness.service import run as run_streaming_eval
from evaluation_harness.service import show as eval_show_cmd

from .workflow_cohort import cohort_create
from .workflow_diff import experiment_diff
from .workflow_doctor import doctor
from .workflow_eval import experiment_explain, experiment_list, experiment_show
from .workflow_helpers import (
    CODEOWNERS_PATH_CANDIDATES,
    DEFAULT_PINNED_ARTIFACT_PATHS,
    EXPERIMENT_MANIFEST_FILENAME,
    _build_cohort_payload,
    _build_repo_profile_settings,
    _build_router_specs,
    _delta,
    _inline_cohort_overrides,
    _iso_utc,
    _load_per_pr_rows,
    _load_report,
    _load_run_context,
    _missing_artifact_paths,
    _parse_dt_option,
    _prefetch_missing_artifacts,
    _read_json,
    _resolve_pr_cutoffs,
    _router_specs_from_spec,
    _run_context_payload,
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
from .workflow_run import experiment_run
from .workflow_spec import experiment_init


cohort_app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)
experiment_app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)
profile_app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)

cohort_app.command("create")(cohort_create)
experiment_app.command("init")(experiment_init)
experiment_app.command("run")(experiment_run)
experiment_app.command("show")(experiment_show)
experiment_app.command("list")(experiment_list)
experiment_app.command("explain")(experiment_explain)
experiment_app.command("diff")(experiment_diff)
profile_app.command("build")(profile_build)

