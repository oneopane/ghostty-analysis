from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from sdlc_core.hashing import stable_hash_json


class LLMSemanticCacheKey(BaseModel):
    repo: str
    entity_type: str
    entity_id: str
    cutoff: str
    artifact_type: str
    version_key: str

    def digest(self) -> str:
        return stable_hash_json(self.model_dump(mode="json"))


@dataclass(frozen=True)
class LLMSemanticCache:
    root: Path

    def _path(self, key: LLMSemanticCacheKey) -> Path:
        return self.root / "llm" / f"{key.digest()}.json"

    def get(self, key: LLMSemanticCacheKey) -> dict[str, object] | None:
        p = self._path(key)
        if not p.exists():
            return None
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None

    def put(self, *, key: LLMSemanticCacheKey, value: dict[str, object]) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(value, sort_keys=True, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )


@dataclass(frozen=True)
class LLMReplayCache:
    cache_dir: str | Path

    def _path(self, key: str) -> Path:
        return Path(self.cache_dir) / f"{key}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        p = self._path(key)
        if not p.exists():
            return None
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None

    def put(self, key: str, value: dict[str, Any]) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(value, sort_keys=True, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
