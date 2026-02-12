#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

run_pytest() {
  if [[ -x "./.venv/bin/pytest" ]]; then
    ./.venv/bin/pytest "$@"
    return
  fi
  echo "[validate] ./.venv/bin/pytest missing; using uv-managed pytest"
  uv run --all-packages pytest "$@"
}

echo "[validate] running targeted feature unit tests"
run_pytest -q \
  packages/inference/tests/test_pr_surface_features.py \
  packages/inference/tests/test_candidate_activity_features.py \
  packages/inference/tests/test_pr_timeline_features.py \
  packages/inference/tests/test_ownership_features.py \
  packages/inference/tests/test_feature_extractor_v1.py \
  packages/inference/tests/test_feature_leakage_and_determinism.py

echo "[validate] running integration/e2e tests for router + eval harness"
run_pytest -q \
  packages/evaluation/tests/test_runner_router_specs.py \
  packages/evaluation/tests/test_runner_import_router.py \
  packages/evaluation/tests/test_end_to_end_run.py

echo "[validate] running full relevant suites"
run_pytest -q \
  packages/inference/tests \
  packages/evaluation/tests

echo "[validate] running docs naming checks"
uv run python scripts/validate_docs_naming.py

echo "[validate] all checks passed"
