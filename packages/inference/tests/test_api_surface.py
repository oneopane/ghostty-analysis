from __future__ import annotations

import repo_routing.api as api


def test_api_surface_exposes_stable_symbols() -> None:
    expected = {
        "RouterSpec",
        "build_router_specs",
        "router_id_for_spec",
        "load_router",
        "HistoryReader",
        "DEFAULT_PINNED_ARTIFACT_PATHS",
        "CODEOWNERS_PATH_CANDIDATES",
        "pinned_artifact_path",
        "build_repo_profile",
        "parse_dt_utc",
        "require_dt_utc",
        "cutoff_key_utc",
    }
    exported = set(getattr(api, "__all__", ()))
    assert expected.issubset(exported)
