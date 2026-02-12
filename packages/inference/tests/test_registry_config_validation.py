from __future__ import annotations

import json
from pathlib import Path

import pytest

from repo_routing.registry import RouterSpec, load_router


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_hybrid_ranker_rejects_invalid_weights_payload(tmp_path: Path) -> None:
    cfg = _write_json(tmp_path / "hybrid.json", {"weights": {"a": "not-a-number"}})
    with pytest.raises(ValueError, match="invalid hybrid_ranker config"):
        load_router(RouterSpec(type="builtin", name="hybrid_ranker", config_path=str(cfg)))


def test_llm_rerank_rejects_invalid_mode_payload(tmp_path: Path) -> None:
    cfg = _write_json(
        tmp_path / "llm.json",
        {"mode": "unsupported", "model_name": "x", "cache_dir": ".cache/x"},
    )
    with pytest.raises(ValueError, match="invalid llm_rerank config"):
        load_router(RouterSpec(type="builtin", name="llm_rerank", config_path=str(cfg)))


def test_stewards_rejects_invalid_config_schema(tmp_path: Path) -> None:
    cfg = _write_json(tmp_path / "stewards.json", {"version": "v0"})
    with pytest.raises(ValueError, match="invalid stewards config"):
        load_router(RouterSpec(type="builtin", name="stewards", config_path=str(cfg)))
