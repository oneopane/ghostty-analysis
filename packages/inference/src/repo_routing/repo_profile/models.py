from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RepoProfileIdentity(BaseModel):
    owner: str
    repo: str
    pr_number: int
    cutoff: datetime
    base_sha: str
    schema_version: str = "v1"
    builder_version: str = "repo_profile_builder.v1"


class ProvenanceEntry(BaseModel):
    source: str = "pinned"
    path: str
    line: int | None = None
    note: str | None = None


class RepoArtifactEntry(BaseModel):
    path: str
    source: str = "pinned"
    content_sha256: str
    size_bytes: int
    detected_type: str


class RepoArtifactManifest(BaseModel):
    files: list[RepoArtifactEntry] = Field(default_factory=list)


class OwnershipNode(BaseModel):
    node_id: str
    kind: Literal["person", "team", "alias", "unknown"] = "unknown"
    name: str
    provenance: list[ProvenanceEntry] = Field(default_factory=list)
    confidence: float = 1.0


class OwnershipEdge(BaseModel):
    relation: Literal["OWNS", "MAINTAINS", "MEMBER_OF"] = "OWNS"
    source_node_id: str
    path_glob: str | None = None
    boundary: str | None = None
    target_node_id: str | None = None
    provenance: list[ProvenanceEntry] = Field(default_factory=list)
    confidence: float = 1.0


class OwnershipGraph(BaseModel):
    nodes: list[OwnershipNode] = Field(default_factory=list)
    edges: list[OwnershipEdge] = Field(default_factory=list)


class BoundaryEntry(BaseModel):
    boundary: str
    path_globs: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    provenance: list[ProvenanceEntry] = Field(default_factory=list)


class BoundaryModel(BaseModel):
    boundaries: list[BoundaryEntry] = Field(default_factory=list)


class PolicySignal(BaseModel):
    key: str
    value: str
    provenance: list[ProvenanceEntry] = Field(default_factory=list)


class PolicySignals(BaseModel):
    signals: list[PolicySignal] = Field(default_factory=list)


class VocabularyEntry(BaseModel):
    token: str
    canonical_intent: str
    gate: str | None = None
    provenance: list[ProvenanceEntry] = Field(default_factory=list)


class RepoVocabulary(BaseModel):
    labels: list[VocabularyEntry] = Field(default_factory=list)
    template_fields: list[VocabularyEntry] = Field(default_factory=list)
    keywords: list[VocabularyEntry] = Field(default_factory=list)


class RepoProfileCoverage(BaseModel):
    artifact_count: int = 0
    codeowners_present: bool = False
    critical_artifacts: list[str] = Field(default_factory=list)
    present_critical_artifacts: list[str] = Field(default_factory=list)
    missing_critical_artifacts: list[str] = Field(default_factory=list)


class RepoProfileQAReport(BaseModel):
    kind: str = "repo_profile_qa"
    version: str = "v1"
    identity: RepoProfileIdentity
    coverage: RepoProfileCoverage
    confidence_distribution: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class RepoProfile(BaseModel):
    kind: str = "repo_profile"
    version: str = "v1"
    identity: RepoProfileIdentity
    artifact_manifest: RepoArtifactManifest
    ownership_graph: OwnershipGraph
    boundary_model: BoundaryModel
    policy_signals: PolicySignals
    vocabulary: RepoVocabulary


class RepoProfileBuildResult(BaseModel):
    profile: RepoProfile
    qa_report: RepoProfileQAReport
