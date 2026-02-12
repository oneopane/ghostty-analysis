from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from repo_routing.boundary.io import read_boundary_artifact, write_boundary_artifact
from repo_routing.boundary.models import (
    BoundaryDef,
    BoundaryModel,
    BoundaryUnit,
    Granularity,
    Membership,
    MembershipMode,
)
from repo_routing.boundary.paths import (
    boundary_manifest_path,
    boundary_model_path,
    boundary_signals_path,
)


def _model() -> BoundaryModel:
    return BoundaryModel(
        strategy_id="hybrid_path_cochange",
        strategy_version="v1",
        repo="octo-org/octo-repo",
        cutoff_utc=datetime(2026, 2, 11, 0, 0, tzinfo=timezone.utc),
        membership_mode=MembershipMode.HARD,
        units=[
            BoundaryUnit(
                unit_id="file:src/b.py", granularity=Granularity.FILE, path="src/b.py"
            ),
            BoundaryUnit(
                unit_id="file:src/a.py", granularity=Granularity.FILE, path="src/a.py"
            ),
        ],
        boundaries=[
            BoundaryDef(
                boundary_id="boundary:ui", name="ui", granularity=Granularity.DIR
            ),
            BoundaryDef(
                boundary_id="boundary:core", name="core", granularity=Granularity.DIR
            ),
        ],
        memberships=[
            Membership(unit_id="file:src/a.py", boundary_id="boundary:core", weight=1.0),
            Membership(unit_id="file:src/b.py", boundary_id="boundary:ui", weight=1.0),
        ],
    )


def test_boundary_io_roundtrip_is_stable(tmp_path) -> None:
    repo = "octo-org/octo-repo"
    cutoff_key = "2026-02-11T00-00-00Z"
    model = _model()

    write_boundary_artifact(
        model=model,
        repo_full_name=repo,
        data_dir=tmp_path,
        cutoff_key=cutoff_key,
    )
    model_path = boundary_model_path(
        repo_full_name=repo,
        data_dir=tmp_path,
        strategy_id=model.strategy_id,
        cutoff_key=cutoff_key,
    )
    first_text = model_path.read_text(encoding="utf-8")

    payload = json.loads(first_text)
    assert [u["unit_id"] for u in payload["units"]] == ["file:src/a.py", "file:src/b.py"]

    out = read_boundary_artifact(
        repo_full_name=repo,
        data_dir=tmp_path,
        strategy_id=model.strategy_id,
        cutoff_key=cutoff_key,
    )
    assert out.model.repo == model.repo
    assert out.manifest.membership_count == 2

    write_boundary_artifact(
        model=out.model,
        repo_full_name=repo,
        data_dir=tmp_path,
        cutoff_key=cutoff_key,
    )
    second_text = model_path.read_text(encoding="utf-8")

    assert first_text == second_text


def test_boundary_read_rejects_tampered_manifest_hash(tmp_path) -> None:
    repo = "octo-org/octo-repo"
    cutoff_key = "2026-02-11T00-00-00Z"
    model = _model()

    write_boundary_artifact(
        model=model,
        repo_full_name=repo,
        data_dir=tmp_path,
        cutoff_key=cutoff_key,
    )

    manifest_path = boundary_manifest_path(
        repo_full_name=repo,
        data_dir=tmp_path,
        strategy_id=model.strategy_id,
        cutoff_key=cutoff_key,
    )
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_payload["model_hash"] = "deadbeef"
    manifest_path.write_text(
        json.dumps(manifest_payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="hash mismatch"):
        read_boundary_artifact(
            repo_full_name=repo,
            data_dir=tmp_path,
            strategy_id=model.strategy_id,
            cutoff_key=cutoff_key,
        )


def test_boundary_signal_parquet_removed_when_empty(tmp_path) -> None:
    repo = "octo-org/octo-repo"
    cutoff_key = "2026-02-11T00-00-00Z"
    model = _model()

    write_boundary_artifact(
        model=model,
        repo_full_name=repo,
        data_dir=tmp_path,
        cutoff_key=cutoff_key,
        signal_rows=[{"signal": "x", "value": 1.0}],
    )
    sig_path = boundary_signals_path(
        repo_full_name=repo,
        data_dir=tmp_path,
        strategy_id=model.strategy_id,
        cutoff_key=cutoff_key,
    )
    assert sig_path.exists()

    write_boundary_artifact(
        model=model,
        repo_full_name=repo,
        data_dir=tmp_path,
        cutoff_key=cutoff_key,
        signal_rows=[],
    )
    assert not sig_path.exists()
