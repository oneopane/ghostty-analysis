from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from .artifacts import BoundaryManifest, BoundaryModelArtifact
from .hash import boundary_model_hash
from .models import BoundaryModel
from .paths import (
    boundary_manifest_path,
    boundary_memberships_path,
    boundary_model_path,
    boundary_signals_path,
)


def _write_json_deterministic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    path.write_text(text, encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_parquet_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path)


def _read_parquet_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    table = pq.read_table(path)
    return table.to_pylist()


def write_boundary_artifact(
    *,
    model: BoundaryModel,
    repo_full_name: str,
    data_dir: str | Path,
    cutoff_key: str,
    signal_rows: list[dict[str, Any]] | None = None,
) -> BoundaryModelArtifact:
    strategy_id = model.strategy_id

    model_path = boundary_model_path(
        repo_full_name=repo_full_name,
        data_dir=data_dir,
        strategy_id=strategy_id,
        cutoff_key=cutoff_key,
    )
    memberships_path = boundary_memberships_path(
        repo_full_name=repo_full_name,
        data_dir=data_dir,
        strategy_id=strategy_id,
        cutoff_key=cutoff_key,
    )
    manifest_path = boundary_manifest_path(
        repo_full_name=repo_full_name,
        data_dir=data_dir,
        strategy_id=strategy_id,
        cutoff_key=cutoff_key,
    )
    signals_path = boundary_signals_path(
        repo_full_name=repo_full_name,
        data_dir=data_dir,
        strategy_id=strategy_id,
        cutoff_key=cutoff_key,
    )

    model_hash = boundary_model_hash(model)
    model_payload = model.model_dump(mode="json")

    memberships_rows = [
        {
            "unit_id": m.unit_id,
            "boundary_id": m.boundary_id,
            "weight": float(m.weight),
        }
        for m in sorted(
            model.memberships,
            key=lambda m: (m.unit_id, m.boundary_id, float(m.weight)),
        )
    ]
    _write_json_deterministic(model_path, model_payload)
    _write_parquet_rows(memberships_path, memberships_rows)

    signal_rows_out = sorted(
        signal_rows or [], key=lambda r: json.dumps(r, sort_keys=True, ensure_ascii=True)
    )
    if signal_rows_out:
        _write_parquet_rows(signals_path, signal_rows_out)

    manifest = BoundaryManifest(
        schema_version=model.schema_version,
        strategy_id=model.strategy_id,
        strategy_version=model.strategy_version,
        repo=model.repo,
        cutoff_utc=model.cutoff_utc,
        model_hash=model_hash,
        unit_count=len(model.units),
        boundary_count=len(model.boundaries),
        membership_count=len(model.memberships),
        metadata={"cutoff_key": cutoff_key},
    )
    _write_json_deterministic(manifest_path, manifest.model_dump(mode="json"))

    return BoundaryModelArtifact(
        model=model,
        manifest=manifest,
        memberships_rows=memberships_rows,
        signal_rows=signal_rows_out,
    )


def read_boundary_artifact(
    *,
    repo_full_name: str,
    data_dir: str | Path,
    strategy_id: str,
    cutoff_key: str,
) -> BoundaryModelArtifact:
    model_path = boundary_model_path(
        repo_full_name=repo_full_name,
        data_dir=data_dir,
        strategy_id=strategy_id,
        cutoff_key=cutoff_key,
    )
    memberships_path = boundary_memberships_path(
        repo_full_name=repo_full_name,
        data_dir=data_dir,
        strategy_id=strategy_id,
        cutoff_key=cutoff_key,
    )
    manifest_path = boundary_manifest_path(
        repo_full_name=repo_full_name,
        data_dir=data_dir,
        strategy_id=strategy_id,
        cutoff_key=cutoff_key,
    )
    signals_path = boundary_signals_path(
        repo_full_name=repo_full_name,
        data_dir=data_dir,
        strategy_id=strategy_id,
        cutoff_key=cutoff_key,
    )

    model = BoundaryModel.model_validate(_read_json(model_path))
    manifest = BoundaryManifest.model_validate(_read_json(manifest_path))
    memberships_rows = _read_parquet_rows(memberships_path)
    signal_rows = _read_parquet_rows(signals_path)

    return BoundaryModelArtifact(
        model=model,
        manifest=manifest,
        memberships_rows=memberships_rows,
        signal_rows=signal_rows,
    )
