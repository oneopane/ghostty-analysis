from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sdlc_core.hashing import stable_hash_json
from sdlc_core.types.prompt import PromptRef, PromptSpec


@dataclass(frozen=True)
class PromptStore:
    root: Path

    def register(self, spec: PromptSpec) -> PromptRef:
        rel = Path("prompts") / spec.prompt_id / f"{spec.prompt_version}.json"
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = spec.model_dump(mode="json")
        path.write_text(
            json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return PromptRef(
            prompt_id=spec.prompt_id,
            prompt_version=spec.prompt_version,
            prompt_hash=stable_hash_json(payload),
        )

    def get(self, *, prompt_id: str, prompt_version: str) -> PromptSpec | None:
        path = self.root / "prompts" / prompt_id / f"{prompt_version}.json"
        if not path.exists():
            return None
        return PromptSpec.model_validate(json.loads(path.read_text(encoding="utf-8")))
