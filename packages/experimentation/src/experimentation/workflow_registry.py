from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CandidateRegistry:
    root: Path

    def _path(self, task_id: str) -> Path:
        return self.root / "registry" / f"{task_id}.json"

    def get(self, *, task_id: str) -> dict[str, object]:
        p = self._path(task_id)
        if not p.exists():
            return {"task_id": task_id, "candidates": [], "champion": None}
        return json.loads(p.read_text(encoding="utf-8"))

    def register(self, *, task_id: str, candidate_ref: str) -> None:
        state = self.get(task_id=task_id)
        candidates = list(state.get("candidates") or [])
        if candidate_ref not in candidates:
            candidates.append(candidate_ref)
        state["candidates"] = candidates
        self._write(task_id=task_id, payload=state)

    def promote(self, *, task_id: str, candidate_ref: str) -> None:
        state = self.get(task_id=task_id)
        if candidate_ref not in list(state.get("candidates") or []):
            raise ValueError("candidate must be registered before promotion")
        state["champion"] = candidate_ref
        self._write(task_id=task_id, payload=state)

    def _write(self, *, task_id: str, payload: dict[str, object]) -> None:
        p = self._path(task_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
