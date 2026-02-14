from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, computed_field

from sdlc_core.hashing import stable_hash_json


class VersionKey(BaseModel):
    operator_id: str
    operator_version: str
    schema_version: str
    model_id: str | None = None
    prompt_id: str | None = None
    prompt_version: str | None = None
    prompt_hash: str | None = None
    temperature: float | None = None
    top_p: float | None = None


class ArtifactEntityRef(BaseModel):
    repo: str
    entity_type: str
    entity_id: str
    entity_version: str | None = None


class ArtifactHeader(BaseModel):
    artifact_type: str
    artifact_version: str
    entity: ArtifactEntityRef
    cutoff: datetime
    created_at: datetime
    code_version: str
    config_hash: str
    version_key: VersionKey
    input_artifact_refs: list[str] = Field(default_factory=list)


class ArtifactRecord(BaseModel):
    header: ArtifactHeader
    payload: dict[str, Any] = Field(default_factory=dict)

    @computed_field(return_type=str)
    @property
    def artifact_id(self) -> str:
        repo_slug = self.header.entity.repo.replace("/", "_")
        digest = stable_hash_json(self.payload)[:16]
        return (
            f"{self.header.artifact_type}__{repo_slug}__"
            f"{self.header.entity.entity_type}__{self.header.entity.entity_id}__{digest}"
        )


class ArtifactRef(BaseModel):
    artifact_id: str
    artifact_type: str
    artifact_version: str
    relative_path: str
    content_sha256: str
    cache_key: str | None = None
