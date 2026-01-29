from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..reporting.formatters import json_dumps, json_dumps_compact
from ..reporting.json import to_json_dict


@dataclass(frozen=True)
class FilesystemStore:
    base_dir: Path

    def write_text(self, rel: str, text: str) -> Path:
        p = self.base_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def write_json(self, rel: str, obj: object) -> Path:
        return self.write_text(rel, json_dumps(to_json_dict(obj)))

    def append_jsonl(self, rel: str, obj: object) -> Path:
        p = self.base_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json_dumps_compact(to_json_dict(obj)))
        return p
