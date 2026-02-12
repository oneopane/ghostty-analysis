from __future__ import annotations

import evaluation_harness.api as api


def test_api_surface_exports_expected_symbols() -> None:
    expected = {
        "run",
        "show",
        "list_runs",
        "explain",
        "EvalRunConfig",
        "EvalDefaults",
        "compute_run_id",
        "RepoProfileRunSettings",
        "RunResult",
    }
    exported = set(getattr(api, "__all__", ()))
    assert expected.issubset(exported)
    for symbol in expected:
        assert hasattr(api, symbol)
