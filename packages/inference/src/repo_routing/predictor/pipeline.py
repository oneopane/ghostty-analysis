from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from ..inputs.models import PRInputBundle
from ..router.base import RouteResult
from .base import FeatureExtractor, Predictor, Ranker


class FeatureCache:
    def get(self, key: str) -> dict[str, object] | None: ...

    def put(self, key: str, value: dict[str, object]) -> None: ...


@dataclass
class JsonFeatureCache(FeatureCache):
    cache_dir: str | Path

    def _path(self, key: str) -> Path:
        return Path(self.cache_dir) / f"{key}.json"

    def get(self, key: str) -> dict[str, object] | None:
        p = self._path(key)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def put(self, key: str, value: dict[str, object]) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(value, sort_keys=True, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )


class PipelinePredictor(Predictor):
    def __init__(
        self,
        *,
        feature_extractor: FeatureExtractor,
        ranker: Ranker,
        cache: FeatureCache | None = None,
    ) -> None:
        self.feature_extractor = feature_extractor
        self.ranker = ranker
        self.cache = cache

        self.last_features: dict[str, object] | None = None
        self.last_cache_key: str | None = None

    @staticmethod
    def _cache_key(input: PRInputBundle) -> str:
        payload = input.model_dump(mode="json")
        data = json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def predict(self, input: PRInputBundle, *, top_k: int) -> RouteResult:
        key = self._cache_key(input)
        self.last_cache_key = key

        cached: dict[str, object] | None = None
        if self.cache is not None:
            cached = self.cache.get(key)

        if cached is not None:
            features = cached
        else:
            features = self.feature_extractor.extract(input)
            if self.cache is not None:
                self.cache.put(key, features)

        self.last_features = features
        return self.ranker.rank(input, features, top_k=top_k)


class DummyLLMRanker(Ranker):
    """Offline test helper for LLM-like ranking.

    Provide a callable that maps `(input, features)` to ordered logins.
    """

    def __init__(self, *, scorer) -> None:  # type: ignore[no-untyped-def]
        self.scorer = scorer

    def rank(
        self,
        input: PRInputBundle,
        features: dict[str, object],
        *,
        top_k: int,
    ) -> RouteResult:
        return self.scorer(input, features, top_k=top_k)
