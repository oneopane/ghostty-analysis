from __future__ import annotations

from experimentation.workflow_quality import evaluate_quality_gates


def test_g5_counts_missing_outputs_not_empty_candidates() -> None:
    rows = [
        {
            "cutoff": "2024-01-01T00:00:00Z",
            "truth_diagnostics": {"window_end": "2024-01-02T00:00:00Z"},
            "repo_profile": {"coverage": {"codeowners_present": True}},
            "routers": {
                "mentions": {
                    "route_result": {
                        "candidates": [],
                    }
                }
            },
        }
    ]
    report = {"extra": {"truth_coverage_counts": {"observed": 1}}}

    out = evaluate_quality_gates(rows=rows, report=report, routers=["mentions"])
    assert out["all_pass"] is True
    g5 = out["gates"]["G5_router_unavailable_rate"]
    assert g5["pass"] is True
    assert g5["value"] == 0.0
    assert g5["empty_candidates_rate"] == 1.0


def test_g5_fails_when_route_result_missing() -> None:
    rows = [
        {
            "cutoff": "2024-01-01T00:00:00Z",
            "truth_diagnostics": {"window_end": "2024-01-02T00:00:00Z"},
            "repo_profile": {"coverage": {"codeowners_present": True}},
            "routers": {
                "mentions": {
                    "route_result": None,
                }
            },
        }
    ]
    report = {"extra": {"truth_coverage_counts": {"observed": 1}}}

    out = evaluate_quality_gates(rows=rows, report=report, routers=["mentions"])
    assert out["all_pass"] is False
    g5 = out["gates"]["G5_router_unavailable_rate"]
    assert g5["pass"] is False
    assert g5["value"] == 1.0
