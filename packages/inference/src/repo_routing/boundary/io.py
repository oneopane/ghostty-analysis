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

_MEMBERSHIP_SCHEMA = pa.schema(
    [
        pa.field("unit_id", pa.string()),
        pa.field("boundary_id", pa.string()),
        pa.field("weight", pa.float64()),
    ]
)


def _write_json_deterministic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    path.write_text(text, encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_parquet_rows(
    path: Path,
    rows: list[dict[str, Any]],
    *,
    schema: pa.Schema | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        table = pa.Table.from_pylist(rows)
    else:
        table = pa.Table.from_pylist([], schema=schema)
    pq.write_table(table, path)


def _read_parquet_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    table = pq.read_table(path)
    return table.to_pylist()


def _canonical_model_payload(model: BoundaryModel) -> dict[str, Any]:
    payload = model.model_dump(mode="json")
    payload["units"] = sorted(
        payload.get("units", []),
        key=lambda u: (
            str(u.get("granularity", "")),
            str(u.get("unit_id", "")),
            str(u.get("path", "") or ""),
            str(u.get("symbol", "") or ""),
            str(u.get("function", "") or ""),
        ),
    )
    payload["boundaries"] = sorted(
        payload.get("boundaries", []),
        key=lambda b: (
            str(b.get("granularity", "")),
            str(b.get("boundary_id", "")),
            str(b.get("name", "")),
        ),
    )
    payload["memberships"] = sorted(
        payload.get("memberships", []),
        key=lambda m: (
            str(m.get("unit_id", "")),
            str(m.get("boundary_id", "")),
            float(m.get("weight", 0.0)),
        ),
    )
    return payload


def write_boundary_artifact(
    *,
    model: BoundaryModel,
    repo_full_name: str,
    data_dir: str | Path,
    cutoff_key: str,
    signal_rows: list[dict[str, Any]] | None = None,
    manifest_metadata: dict[str, Any] | None = None,
) -> BoundaryModelArtifact:
    if model.repo != repo_full_name:
        raise ValueError(
            f"repo mismatch: model.repo={model.repo!r} repo_full_name={repo_full_name!r}"
        )

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
    model_payload = _canonical_model_payload(model)

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
    _write_parquet_rows(memberships_path, memberships_rows, schema=_MEMBERSHIP_SCHEMA)

    signal_rows_out = sorted(
        signal_rows or [], key=lambda r: json.dumps(r, sort_keys=True, ensure_ascii=True)
    )
    if signal_rows_out:
        _write_parquet_rows(signals_path, signal_rows_out)
    elif signals_path.exists():
        signals_path.unlink()

    metadata = dict(manifest_metadata or {})
    metadata["cutoff_key"] = cutoff_key
    diagnostics = dict((model.metadata or {}).get("diagnostics") or {})
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
        metadata=metadata,
        parser_coverage={
            "enabled": bool((model.metadata or {}).get("parser_enabled", False)),
            "backend_id": (model.metadata or {}).get("parser_backend_id"),
            "backend_version": (model.metadata or {}).get("parser_backend_version"),
            "signal_files": int((model.metadata or {}).get("parser_signal_files", 0) or 0),
            "diagnostics": list((model.metadata or {}).get("parser_diagnostics", [])),
            "file_count": int(diagnostics.get("file_count", 0) or 0),
            "coverage_ratio": (
                float((model.metadata or {}).get("parser_signal_files", 0) or 0)
                / float(max(int(diagnostics.get("file_count", 0) or 0), 1))
            ),
        },
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

    expected_hash = boundary_model_hash(model)
    if manifest.model_hash != expected_hash:
        raise ValueError(
            f"boundary manifest hash mismatch: expected={expected_hash} got={manifest.model_hash}"
        )
    if manifest.repo != repo_full_name or model.repo != repo_full_name:
        raise ValueError(
            f"boundary repo mismatch for artifact read: expected={repo_full_name} model={model.repo} manifest={manifest.repo}"
        )
    if manifest.strategy_id != strategy_id:
        raise ValueError(
            f"boundary strategy mismatch for artifact read: expected={strategy_id} got={manifest.strategy_id}"
        )
    if manifest.unit_count != len(model.units):
        raise ValueError("boundary manifest unit_count does not match model")
    if manifest.boundary_count != len(model.boundaries):
        raise ValueError("boundary manifest boundary_count does not match model")
    if manifest.membership_count != len(model.memberships):
        raise ValueError("boundary manifest membership_count does not match model")

    return BoundaryModelArtifact(
        model=model,
        manifest=manifest,
        memberships_rows=memberships_rows,
        signal_rows=signal_rows,
    )
