from __future__ import annotations

from typing import Any, Protocol

from ..inputs.models import PRInputBundle
from ..router.base import RouteResult


class Predictor(Protocol):
    def predict(self, input: PRInputBundle, *, top_k: int) -> RouteResult: ...


class FeatureExtractor(Protocol):
    def extract(self, input: PRInputBundle) -> dict[str, Any]: ...


class Ranker(Protocol):
    def rank(
        self,
        input: PRInputBundle,
        features: dict[str, Any],
        *,
        top_k: int,
    ) -> RouteResult: ...
