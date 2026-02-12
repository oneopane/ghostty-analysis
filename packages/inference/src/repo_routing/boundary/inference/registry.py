from __future__ import annotations

from typing import Callable

from .base import BoundaryInferenceStrategy
from .hybrid_path_cochange_v1 import HybridPathCochangeV1


BoundaryStrategyFactory = Callable[[], BoundaryInferenceStrategy]

_BOUNDARY_STRATEGY_FACTORIES: dict[str, BoundaryStrategyFactory] = {}
_BOUNDARY_STRATEGY_ALIASES: dict[str, str] = {}


def register_boundary_strategy(
    *,
    strategy_id: str,
    factory: BoundaryStrategyFactory,
    aliases: tuple[str, ...] = (),
) -> None:
    key = strategy_id.strip().lower()
    if not key:
        raise ValueError("strategy_id cannot be empty")
    _BOUNDARY_STRATEGY_FACTORIES[key] = factory
    for alias in aliases:
        alias_key = alias.strip().lower()
        if alias_key:
            _BOUNDARY_STRATEGY_ALIASES[alias_key] = key


def available_boundary_strategies() -> tuple[str, ...]:
    return tuple(sorted(_BOUNDARY_STRATEGY_FACTORIES))


def _resolve_strategy_key(strategy_id: str) -> str:
    sid = strategy_id.strip().lower()
    if sid in _BOUNDARY_STRATEGY_FACTORIES:
        return sid
    return _BOUNDARY_STRATEGY_ALIASES.get(sid, sid)


def get_boundary_strategy(strategy_id: str) -> BoundaryInferenceStrategy:
    key = _resolve_strategy_key(strategy_id)
    factory = _BOUNDARY_STRATEGY_FACTORIES.get(key)
    if factory is not None:
        return factory()
    raise KeyError(f"unknown boundary strategy: {strategy_id}")


register_boundary_strategy(
    strategy_id="hybrid_path_cochange.v1",
    factory=HybridPathCochangeV1,
    aliases=("hybrid.v1",),
)
