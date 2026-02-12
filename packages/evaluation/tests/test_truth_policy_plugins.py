from __future__ import annotations

import pytest

from evaluation_harness.truth_policy import resolve_truth_policies


def test_truth_policy_plugin_loads_when_allowlisted(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    pkg = tmp_path / "tmp_truth_plugins"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "custom.py").write_text(
        """
def build_policy():
    return {
        "id": "custom_policy_v1",
        "version": "v1",
        "target_kind": "actor_set",
        "window_seconds": 1800,
        "sources": ["reviews"],
        "filters": {"exclude_author": True, "exclude_bots": True},
        "selector": "first",
        "status_rules": [{"if": "default", "status": "unknown_due_to_ingestion_gap"}],
    }
""",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    resolved = resolve_truth_policies(
        policy_ids=("custom_policy_v1",),
        plugin_import_paths=("tmp_truth_plugins.custom:build_policy",),
        plugin_allowlist_prefixes=("tmp_truth_plugins.",),
    )
    assert set(resolved) == {"custom_policy_v1"}
    assert resolved["custom_policy_v1"].source == "plugin"
    assert resolved["custom_policy_v1"].source_ref == "tmp_truth_plugins.custom:build_policy"


def test_truth_policy_plugin_rejected_when_not_allowlisted() -> None:
    with pytest.raises(ValueError, match="not allowlisted"):
        resolve_truth_policies(
            policy_ids=("first_response_v1",),
            plugin_import_paths=("os:path",),
            plugin_allowlist_prefixes=("evaluation_harness.truth_plugins.",),
        )
