from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class AreaMembershipModelArtifact(BaseModel):
    kind: str = "mixed_membership_model"
    version: str = "mm.v1"
    model_type: str = "nmf"

    repo: str
    cutoff: datetime

    config: dict[str, Any] = Field(default_factory=dict)

    users: list[str] = Field(default_factory=list)
    areas: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)

    user_role_mix: dict[str, list[float]] = Field(default_factory=dict)
    role_area_mix: dict[str, dict[str, float]] = Field(default_factory=dict)

    diagnostics: dict[str, Any] = Field(default_factory=dict)
    model_hash: str = ""


def _canonical_payload(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def compute_model_hash(payload: dict[str, Any]) -> str:
    core = {
        "repo": payload.get("repo"),
        "cutoff": payload.get("cutoff"),
        "config": payload.get("config"),
        "users": payload.get("users"),
        "areas": payload.get("areas"),
        "roles": payload.get("roles"),
        "user_role_mix": payload.get("user_role_mix"),
        "role_area_mix": payload.get("role_area_mix"),
    }
    return hashlib.sha256(_canonical_payload(core).encode("utf-8")).hexdigest()


def write_model_artifact(path: str | Path, artifact: AreaMembershipModelArtifact) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    data = artifact.model_dump(mode="json")
    if not data.get("model_hash"):
        data["model_hash"] = compute_model_hash(data)

    payload = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    p.write_text(payload, encoding="utf-8")
    return p


def read_model_artifact(path: str | Path) -> AreaMembershipModelArtifact:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    return AreaMembershipModelArtifact.model_validate(data)
