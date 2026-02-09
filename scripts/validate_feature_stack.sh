#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -x "./.venv/bin/pytest" ]]; then
  echo "error: ./.venv/bin/pytest not found or not executable" >&2
  exit 1
fi

echo "[validate] running targeted feature unit tests"
./.venv/bin/pytest -q \
  packages/repo-routing/tests/test_pr_surface_features.py \
  packages/repo-routing/tests/test_candidate_activity_features.py \
  packages/repo-routing/tests/test_pr_timeline_features.py \
  packages/repo-routing/tests/test_ownership_features.py \
  packages/repo-routing/tests/test_feature_extractor_v1.py \
  packages/repo-routing/tests/test_feature_leakage_and_determinism.py

echo "[validate] running integration/e2e tests for router + eval harness"
./.venv/bin/pytest -q \
  packages/evaluation-harness/tests/test_runner_router_specs.py \
  packages/evaluation-harness/tests/test_runner_import_router.py \
  packages/evaluation-harness/tests/test_end_to_end_run.py

echo "[validate] running full relevant suites"
./.venv/bin/pytest -q \
  packages/repo-routing/tests \
  packages/evaluation-harness/tests

echo "[validate] all checks passed"
