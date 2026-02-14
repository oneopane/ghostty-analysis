from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sdlc_core.hashing import stable_hash_json
from sdlc_core.store.artifact_index import ArtifactIndexRow, ArtifactIndexStore
from sdlc_core.types.artifact import ArtifactRecord, ArtifactRef


@dataclass(frozen=True)
class FileArtifactStore:
    root: Path

    def _index(self) -> ArtifactIndexStore:
        return ArtifactIndexStore(path=self.root / "artifact_index.jsonl")

    def write_json(self, *, rel_path: str, payload: Any) -> Path:
        p = self.root / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return p

    def read_json(self, *, rel_path: str) -> dict[str, Any] | None:
        p = self.root / rel_path
        if not p.exists():
            return None
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None

    def write_artifact(self, *, record: ArtifactRecord, cache_key: str | None = None) -> ArtifactRef:
        rel = f"artifacts/{record.header.artifact_type}/{record.artifact_id}.json"
        payload = record.model_dump(mode="json")
        p = self.write_json(rel_path=rel, payload=payload)
        content_hash = stable_hash_json(payload)

        ref = ArtifactRef(
            artifact_id=record.artifact_id,
            artifact_type=record.header.artifact_type,
            artifact_version=record.header.artifact_version,
            relative_path=rel,
            content_sha256=content_hash,
            cache_key=cache_key,
        )

        self._index().append(
            ArtifactIndexRow(
                artifact_id=ref.artifact_id,
                artifact_type=ref.artifact_type,
                artifact_version=ref.artifact_version,
                relative_path=ref.relative_path,
                content_sha256=ref.content_sha256,
                cache_key=ref.cache_key,
            )
        )

        return ref

    def find_cached(self, *, cache_key: str) -> ArtifactRef | None:
        rows = self._index().list_rows()
        for row in reversed(rows):
            if row.cache_key == cache_key:
                return ArtifactRef(
                    artifact_id=row.artifact_id,
                    artifact_type=row.artifact_type,
                    artifact_version=row.artifact_version,
                    relative_path=row.relative_path,
                    content_sha256=row.content_sha256,
                    cache_key=row.cache_key,
                )
        return None
