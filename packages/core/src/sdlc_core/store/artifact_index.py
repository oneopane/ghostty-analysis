from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel


class ArtifactIndexRow(BaseModel):
    artifact_id: str
    artifact_type: str
    artifact_version: str
    relative_path: str
    content_sha256: str
    cache_key: str | None = None


@dataclass(frozen=True)
class ArtifactIndexStore:
    path: Path

    def append(self, row: ArtifactIndexRow) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    row.model_dump(mode="json"),
                    sort_keys=True,
                    ensure_ascii=True,
                )
            )
            f.write("\n")

    def list_rows(self, *, artifact_type: str | None = None) -> list[ArtifactIndexRow]:
        if not self.path.exists():
            return []

        rows: list[ArtifactIndexRow] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = ArtifactIndexRow.model_validate(json.loads(line))
            if artifact_type is not None and row.artifact_type != artifact_type:
                continue
            rows.append(row)
        return rows
