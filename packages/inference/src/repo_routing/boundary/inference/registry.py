from __future__ import annotations

from .base import BoundaryInferenceStrategy
from .hybrid_path_cochange_v1 import HybridPathCochangeV1


def get_boundary_strategy(strategy_id: str) -> BoundaryInferenceStrategy:
    sid = strategy_id.strip().lower()
    if sid == "hybrid_path_cochange.v1":
        return HybridPathCochangeV1()
    raise KeyError(f"unknown boundary strategy: {strategy_id}")
