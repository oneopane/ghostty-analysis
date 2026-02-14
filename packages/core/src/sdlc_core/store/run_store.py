from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sdlc_core.types.run import RunManifest, RunMetadata


@dataclass(frozen=True)
class FileRunStore:
    root: Path

    def write_run_metadata(self, *, rel_path: str, metadata: RunMetadata) -> Path:
        p = self.root / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(metadata.model_dump(mode="json"), sort_keys=True, ensure_ascii=True, indent=2)
            + "\n",
            encoding="utf-8",
        )
        return p

    def write_run_manifest(self, *, rel_path: str, manifest: RunManifest) -> Path:
        p = self.root / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(manifest.model_dump(mode="json"), sort_keys=True, ensure_ascii=True, indent=2)
            + "\n",
            encoding="utf-8",
        )
        return p

    def read_run_manifest(self, *, rel_path: str) -> RunManifest | None:
        p = self.root / rel_path
        if not p.exists():
            return None
        return RunManifest.model_validate(json.loads(p.read_text(encoding="utf-8")))
