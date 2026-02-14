# Artifact-Native SDLC Rewrite (V2) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current run-output-centric routing/evaluation flow with an artifact-native, cutoff-safe, cache-first architecture where prompts, semantic artifacts, operators, and promotion state are first-class versioned objects.

**Architecture:** Build new contracts in `packages/core` first (artifact/prompt/run/operator schemas + stores), then cut inference/evaluation/experimentation over to those contracts in a big-bang migration. Evaluation becomes artifact-native (reads/writes `ArtifactRef`), and human-friendly outputs (`per_pr.jsonl`, `report.json`) are derived views. No backward compatibility for old runs.

**Tech Stack:** Python 3.11+, Pydantic v2, Typer CLI, pytest, uv workspace, filesystem + JSONL indexes, SQLite (`history.sqlite`) for source-of-truth events.

---

## Execution context (read before Task 1)

- This plan **must be executed in a dedicated worktree**.
- Use skills:
  - `@superpowers:executing-plans` (required)
  - `@jujutsu-vcs` (for frequent commits; repo convention prefers `jj`)
- Keep TDD strict: fail -> implement minimum -> pass -> commit.
- Keep each code change minimal and reversible.

## Reference docs to keep open

- `AGENTS.md`
- `docs/system-transcript.md`
- `docs/attention-routing/architecture.md`
- `docs/codebase_map_pack/contracts.md`
- `packages/core/README.md`
- `packages/inference/README.md`
- `packages/evaluation/README.md`
- `packages/experimentation/README.md`

## Workspace setup commands (run once)

```bash
uv venv
uv sync
uv run --project packages/cli repo --help
```

Expected: commands succeed with no import errors.

---

### Task 1: Define V2 artifact type contracts in core

**Files:**
- Create: `packages/core/tests/test_artifact_types_v2.py`
- Modify: `packages/core/src/sdlc_core/types/artifact.py`
- Modify: `packages/core/src/sdlc_core/types/__init__.py`

**Step 1: Write the failing test**

```python
from datetime import datetime, timezone

from sdlc_core.types.artifact import (
    ArtifactEntityRef,
    ArtifactHeader,
    ArtifactRecord,
    VersionKey,
)


def test_artifact_record_has_stable_artifact_id() -> None:
    header = ArtifactHeader(
        artifact_type="route_result",
        artifact_version="v2",
        entity=ArtifactEntityRef(
            repo="acme/widgets",
            entity_type="pull_request",
            entity_id="42",
            entity_version="sha:abc123",
        ),
        cutoff=datetime(2026, 2, 1, tzinfo=timezone.utc),
        created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        code_version="deadbeef",
        config_hash="cfg123",
        version_key=VersionKey(
            operator_id="router.llm_rerank",
            operator_version="v2",
            schema_version="v2",
        ),
        input_artifact_refs=[],
    )
    rec = ArtifactRecord(header=header, payload={"top_k": 5})
    assert rec.artifact_id.startswith("route_result__acme_widgets__pull_request__42__")
```

**Step 2: Run test to verify it fails**

Run: `uv run --project packages/core pytest packages/core/tests/test_artifact_types_v2.py::test_artifact_record_has_stable_artifact_id -v`
Expected: FAIL (`ImportError` or missing model fields/properties).

**Step 3: Write minimal implementation**

```python
# packages/core/src/sdlc_core/types/artifact.py
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
```

**Step 4: Run test to verify it passes**

Run: `uv run --project packages/core pytest packages/core/tests/test_artifact_types_v2.py::test_artifact_record_has_stable_artifact_id -v`
Expected: PASS.

**Step 5: Commit**

```bash
jj status
jj commit -m "feat(core): add v2 artifact contracts"
```

---

### Task 2: Add append-only artifact index store

**Files:**
- Create: `packages/core/src/sdlc_core/store/artifact_index.py`
- Create: `packages/core/tests/test_artifact_index_store.py`
- Modify: `packages/core/src/sdlc_core/store/__init__.py`

**Step 1: Write the failing test**

```python
from sdlc_core.store.artifact_index import ArtifactIndexRow, ArtifactIndexStore


def test_artifact_index_append_and_filter(tmp_path) -> None:
    idx = ArtifactIndexStore(path=tmp_path / "artifact_index.jsonl")
    idx.append(
        ArtifactIndexRow(
            artifact_id="a1",
            artifact_type="route_result",
            artifact_version="v2",
            relative_path="artifacts/route_result/a1.json",
            content_sha256="abc",
            cache_key="k1",
        )
    )
    idx.append(
        ArtifactIndexRow(
            artifact_id="a2",
            artifact_type="truth_label",
            artifact_version="v2",
            relative_path="artifacts/truth_label/a2.json",
            content_sha256="def",
            cache_key=None,
        )
    )
    rows = idx.list_rows(artifact_type="route_result")
    assert [r.artifact_id for r in rows] == ["a1"]
```

**Step 2: Run test to verify it fails**

Run: `uv run --project packages/core pytest packages/core/tests/test_artifact_index_store.py::test_artifact_index_append_and_filter -v`
Expected: FAIL (`ModuleNotFoundError: artifact_index`).

**Step 3: Write minimal implementation**

```python
# packages/core/src/sdlc_core/store/artifact_index.py
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
            f.write(json.dumps(row.model_dump(mode="json"), sort_keys=True, ensure_ascii=True))
            f.write("\n")

    def list_rows(self, *, artifact_type: str | None = None) -> list[ArtifactIndexRow]:
        if not self.path.exists():
            return []
        out: list[ArtifactIndexRow] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = ArtifactIndexRow.model_validate(json.loads(line))
            if artifact_type is not None and row.artifact_type != artifact_type:
                continue
            out.append(row)
        return out
```

**Step 4: Run test to verify it passes**

Run: `uv run --project packages/core pytest packages/core/tests/test_artifact_index_store.py::test_artifact_index_append_and_filter -v`
Expected: PASS.

**Step 5: Commit**

```bash
jj status
jj commit -m "feat(core): add append-only artifact index store"
```

---

### Task 3: Upgrade FileArtifactStore to artifact-native write/read/cache lookup

**Files:**
- Create: `packages/core/tests/test_file_artifact_store_v2.py`
- Modify: `packages/core/src/sdlc_core/store/artifact_store.py`

**Step 1: Write the failing test**

```python
from datetime import datetime, timezone

from sdlc_core.store.artifact_store import FileArtifactStore
from sdlc_core.types.artifact import ArtifactEntityRef, ArtifactHeader, ArtifactRecord, VersionKey


def test_file_artifact_store_write_and_cache_lookup(tmp_path) -> None:
    store = FileArtifactStore(root=tmp_path)
    record = ArtifactRecord(
        header=ArtifactHeader(
            artifact_type="llm_extract",
            artifact_version="v1",
            entity=ArtifactEntityRef(repo="acme/widgets", entity_type="comment", entity_id="99"),
            cutoff=datetime(2026, 2, 1, tzinfo=timezone.utc),
            created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
            code_version="deadbeef",
            config_hash="cfg",
            version_key=VersionKey(operator_id="extractor", operator_version="v1", schema_version="v1"),
            input_artifact_refs=[],
        ),
        payload={"label": "out_of_scope"},
    )

    ref = store.write_artifact(record=record, cache_key="comment:99:v1")
    hit = store.find_cached(cache_key="comment:99:v1")

    assert hit is not None
    assert hit.artifact_id == ref.artifact_id
```

**Step 2: Run test to verify it fails**

Run: `uv run --project packages/core pytest packages/core/tests/test_file_artifact_store_v2.py::test_file_artifact_store_write_and_cache_lookup -v`
Expected: FAIL (`AttributeError: write_artifact/find_cached`).

**Step 3: Write minimal implementation**

```python
# packages/core/src/sdlc_core/store/artifact_store.py
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sdlc_core.hashing import stable_hash_json
from sdlc_core.store.artifact_index import ArtifactIndexRow, ArtifactIndexStore
from sdlc_core.types.artifact import ArtifactRecord, ArtifactRef


@dataclass(frozen=True)
class FileArtifactStore:
    root: Path

    def _index(self) -> ArtifactIndexStore:
        return ArtifactIndexStore(path=self.root / "artifact_index.jsonl")

    def write_artifact(self, *, record: ArtifactRecord, cache_key: str | None = None) -> ArtifactRef:
        rel = f"artifacts/{record.header.artifact_type}/{record.artifact_id}.json"
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = record.model_dump(mode="json")
        content_hash = stable_hash_json(payload)
        p.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

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
                cache_key=cache_key,
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
```

**Step 4: Run test to verify it passes**

Run: `uv run --project packages/core pytest packages/core/tests/test_file_artifact_store_v2.py::test_file_artifact_store_write_and_cache_lookup -v`
Expected: PASS.

**Step 5: Commit**

```bash
jj status
jj commit -m "feat(core): make artifact store artifact-native with cache lookup"
```

---

### Task 4: Add first-class PromptSpec and PromptStore

**Files:**
- Create: `packages/core/src/sdlc_core/store/prompt_store.py`
- Create: `packages/core/tests/test_prompt_store.py`
- Modify: `packages/core/src/sdlc_core/types/prompt.py`
- Modify: `packages/core/src/sdlc_core/store/__init__.py`
- Modify: `packages/core/src/sdlc_core/types/__init__.py`

**Step 1: Write the failing test**

```python
from sdlc_core.store.prompt_store import PromptStore
from sdlc_core.types.prompt import PromptSpec


def test_prompt_store_register_and_get(tmp_path) -> None:
    store = PromptStore(root=tmp_path)
    spec = PromptSpec(
        prompt_id="reviewer_rerank",
        prompt_version="v1",
        template="Rank candidates for PR {{ pr_number }}",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )
    ref = store.register(spec)
    loaded = store.get(prompt_id="reviewer_rerank", prompt_version="v1")

    assert ref.prompt_id == "reviewer_rerank"
    assert loaded is not None
    assert loaded.template.startswith("Rank candidates")
```

**Step 2: Run test to verify it fails**

Run: `uv run --project packages/core pytest packages/core/tests/test_prompt_store.py::test_prompt_store_register_and_get -v`
Expected: FAIL (`ModuleNotFoundError` or missing `PromptSpec`).

**Step 3: Write minimal implementation**

```python
# packages/core/src/sdlc_core/types/prompt.py
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class PromptSpec(BaseModel):
    prompt_id: str
    prompt_version: str
    template: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


class PromptRef(BaseModel):
    prompt_id: str
    prompt_version: str
    prompt_hash: str
    schema_version: str = "v1"
```

```python
# packages/core/src/sdlc_core/store/prompt_store.py
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
        path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
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
```

**Step 4: Run test to verify it passes**

Run: `uv run --project packages/core pytest packages/core/tests/test_prompt_store.py::test_prompt_store_register_and_get -v`
Expected: PASS.

**Step 5: Commit**

```bash
jj status
jj commit -m "feat(core): add prompt spec and prompt store"
```

---

### Task 5: Add RunManifest V2 and upgrade run store

**Files:**
- Create: `packages/core/tests/test_run_store_v2.py`
- Modify: `packages/core/src/sdlc_core/types/run.py`
- Modify: `packages/core/src/sdlc_core/store/run_store.py`
- Modify: `packages/core/src/sdlc_core/types/__init__.py`

**Step 1: Write the failing test**

```python
from datetime import datetime, timezone

from sdlc_core.store.run_store import FileRunStore
from sdlc_core.types.run import RunManifest


def test_run_store_roundtrip_manifest(tmp_path) -> None:
    store = FileRunStore(root=tmp_path)
    manifest = RunManifest(
        run_id="r1",
        run_kind="evaluation",
        generated_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        repo="acme/widgets",
        task_id="reviewer_routing",
        routers=["mentions", "llm_rerank"],
        produced_artifact_refs=["artifact://route_result/a1"],
        db_max_event_occurred_at="2026-01-31T00:00:00Z",
        db_max_watermark_updated_at="2026-02-01T00:00:00Z",
    )
    path = store.write_run_manifest(rel_path="run_manifest.json", manifest=manifest)
    loaded = store.read_run_manifest(rel_path="run_manifest.json")

    assert path.exists()
    assert loaded is not None
    assert loaded.task_id == "reviewer_routing"
```

**Step 2: Run test to verify it fails**

Run: `uv run --project packages/core pytest packages/core/tests/test_run_store_v2.py::test_run_store_roundtrip_manifest -v`
Expected: FAIL (missing `RunManifest` and methods).

**Step 3: Write minimal implementation**

```python
# packages/core/src/sdlc_core/types/run.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RunManifest(BaseModel):
    run_id: str
    run_kind: str
    generated_at: datetime
    repo: str
    task_id: str
    routers: list[str] = Field(default_factory=list)
    produced_artifact_refs: list[str] = Field(default_factory=list)
    db_max_event_occurred_at: str | None = None
    db_max_watermark_updated_at: str | None = None
    llm_usage: dict[str, object] = Field(default_factory=dict)
    config_hash: str | None = None
    code_version: str | None = None
```

```python
# packages/core/src/sdlc_core/store/run_store.py
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sdlc_core.types.run import RunManifest


@dataclass(frozen=True)
class FileRunStore:
    root: Path

    def write_run_manifest(self, *, rel_path: str, manifest: RunManifest) -> Path:
        p = self.root / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(manifest.model_dump(mode="json"), sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return p

    def read_run_manifest(self, *, rel_path: str) -> RunManifest | None:
        p = self.root / rel_path
        if not p.exists():
            return None
        return RunManifest.model_validate(json.loads(p.read_text(encoding="utf-8")))
```

**Step 4: Run test to verify it passes**

Run: `uv run --project packages/core pytest packages/core/tests/test_run_store_v2.py::test_run_store_roundtrip_manifest -v`
Expected: PASS.

**Step 5: Commit**

```bash
jj status
jj commit -m "feat(core): add run manifest v2 and run store roundtrip"
```

---

### Task 6: Cut inference artifact writer over to FileArtifactStore

**Files:**
- Create: `packages/inference/tests/test_artifact_writer_v2.py`
- Modify: `packages/inference/src/repo_routing/artifacts/writer.py`
- Modify: `packages/inference/src/repo_routing/artifacts/models.py`

**Step 1: Write the failing test**

```python
from datetime import datetime, timezone

from repo_routing.artifacts.writer import ArtifactWriter
from repo_routing.router.base import RouteResult


def test_route_write_creates_artifact_index_entry(tmp_path) -> None:
    writer = ArtifactWriter(repo="acme/widgets", data_dir=tmp_path, run_id="run-v2")
    result = RouteResult(repo="acme/widgets", pr_number=7, as_of=datetime(2026, 2, 1, tzinfo=timezone.utc))

    ref = writer.write_route_result_v2(router_id="mentions", result=result, meta={})

    assert ref.artifact_type == "route_result"
    idx = tmp_path / "github" / "acme" / "widgets" / "eval" / "run-v2" / "artifact_index.jsonl"
    assert idx.exists()
```

**Step 2: Run test to verify it fails**

Run: `uv run --project packages/inference pytest packages/inference/tests/test_artifact_writer_v2.py::test_route_write_creates_artifact_index_entry -v`
Expected: FAIL (`AttributeError: write_route_result_v2`).

**Step 3: Write minimal implementation**

```python
# in ArtifactWriter.__init__
from sdlc_core.store import FileArtifactStore
from sdlc_core.types.artifact import ArtifactEntityRef, ArtifactHeader, ArtifactRecord, VersionKey

self._store = FileArtifactStore(root=repo_eval_run_dir(repo_full_name=self.repo, data_dir=self.data_dir, run_id=self.run_id))

# new method

def write_route_result_v2(self, *, router_id: str, result: RouteResult, meta: dict[str, object]):
    record = ArtifactRecord(
        header=ArtifactHeader(
            artifact_type="route_result",
            artifact_version="v2",
            entity=ArtifactEntityRef(
                repo=result.repo,
                entity_type="pull_request",
                entity_id=str(result.pr_number),
                entity_version=result.as_of.isoformat(),
            ),
            cutoff=result.as_of,
            created_at=result.as_of,
            code_version="unknown",
            config_hash="unknown",
            version_key=VersionKey(
                operator_id=f"router.{router_id}",
                operator_version="v2",
                schema_version="v2",
            ),
            input_artifact_refs=[],
        ),
        payload={"router_id": router_id, "result": result.model_dump(mode="json"), "meta": meta},
    )
    return self._store.write_artifact(record=record)
```

**Step 4: Run test to verify it passes**

Run: `uv run --project packages/inference pytest packages/inference/tests/test_artifact_writer_v2.py::test_route_write_creates_artifact_index_entry -v`
Expected: PASS.

**Step 5: Commit**

```bash
jj status
jj commit -m "feat(inference): write route artifacts via core artifact store"
```

---

### Task 7: Replace LLM replay cache with semantic artifact cache + provenance

**Files:**
- Create: `packages/inference/tests/test_llm_semantic_cache.py`
- Modify: `packages/inference/src/repo_routing/router/llm_cache.py`
- Modify: `packages/inference/src/repo_routing/router/llm_rerank.py`

**Step 1: Write the failing test**

```python
from repo_routing.router.llm_cache import LLMSemanticCache, LLMSemanticCacheKey


def test_llm_semantic_cache_roundtrip(tmp_path) -> None:
    cache = LLMSemanticCache(root=tmp_path)
    key = LLMSemanticCacheKey(
        repo="acme/widgets",
        entity_type="pull_request",
        entity_id="7",
        cutoff="2026-02-01T00:00:00Z",
        artifact_type="llm_rerank_response",
        version_key="model=dummy|prompt=abc|temp=0",
    )

    assert cache.get(key) is None
    cache.put(key=key, value={"items": []})
    assert cache.get(key) == {"items": []}
```

**Step 2: Run test to verify it fails**

Run: `uv run --project packages/inference pytest packages/inference/tests/test_llm_semantic_cache.py::test_llm_semantic_cache_roundtrip -v`
Expected: FAIL (missing classes).

**Step 3: Write minimal implementation**

```python
# packages/inference/src/repo_routing/router/llm_cache.py
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

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
        p.write_text(json.dumps(value, sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
```

Also update `LLMRerankRouter` to store `prompt_id`, `prompt_version`, `prompt_hash`, `model`, `temperature` in `last_provenance`.

**Step 4: Run test to verify it passes**

Run: `uv run --project packages/inference pytest packages/inference/tests/test_llm_semantic_cache.py::test_llm_semantic_cache_roundtrip -v`
Expected: PASS.

**Step 5: Commit**

```bash
jj status
jj commit -m "feat(inference): add semantic cache keys for llm artifacts"
```

---

### Task 8: Introduce operator abstraction and registry bridge

**Files:**
- Create: `packages/inference/src/repo_routing/operators/base.py`
- Create: `packages/inference/src/repo_routing/operators/registry.py`
- Create: `packages/inference/tests/test_operator_registry.py`
- Modify: `packages/inference/src/repo_routing/registry.py`
- Modify: `packages/inference/src/repo_routing/api.py`

**Step 1: Write the failing test**

```python
from repo_routing.operators.registry import list_operator_ids


def test_builtin_router_operators_are_registered() -> None:
    ids = list_operator_ids(task_id="reviewer_routing")
    assert "router.mentions" in ids
    assert "router.llm_rerank" in ids
```

**Step 2: Run test to verify it fails**

Run: `uv run --project packages/inference pytest packages/inference/tests/test_operator_registry.py::test_builtin_router_operators_are_registered -v`
Expected: FAIL (module or function missing).

**Step 3: Write minimal implementation**

```python
# packages/inference/src/repo_routing/operators/base.py
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class OperatorRole(StrEnum):
    extractor = "extractor"
    summarizer = "summarizer"
    router = "router"
    taxonomy_builder = "taxonomy_builder"
    aligner = "aligner"
    policy_elicitor = "policy_elicitor"
    synthesizer = "synthesizer"
    end_to_end_predictor = "end_to_end_predictor"


class OperatorSpec(BaseModel):
    operator_id: str
    role: OperatorRole
    task_id: str
    requires_cutoff_safe_inputs: bool = True
    cost_class: str = "cheap"
```

```python
# packages/inference/src/repo_routing/operators/registry.py
from __future__ import annotations

from repo_routing.registry import builtin_router_names


def list_operator_ids(*, task_id: str) -> list[str]:
    if task_id != "reviewer_routing":
        return []
    return [f"router.{name}" for name in builtin_router_names()]
```

**Step 4: Run test to verify it passes**

Run: `uv run --project packages/inference pytest packages/inference/tests/test_operator_registry.py::test_builtin_router_operators_are_registered -v`
Expected: PASS.

**Step 5: Commit**

```bash
jj status
jj commit -m "feat(inference): add operator abstraction and registry bridge"
```

---

### Task 9: Implement cutoff horizon check command (`repo evaluation cutoff --cutoff ...`)

**Files:**
- Create: `packages/evaluation/tests/test_cutoff_horizon_check.py`
- Modify: `packages/evaluation/src/evaluation_harness/service.py`
- Modify: `packages/evaluation/src/evaluation_harness/cli/app.py`

**Step 1: Write the failing test**

```python
from evaluation_harness.cli.app import app
from typer.testing import CliRunner

from .fixtures.build_min_db import build_min_db


def test_cutoff_horizon_check_returns_pass_or_fail(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "cutoff",
            "--repo",
            db.repo,
            "--cutoff",
            "1999-01-01T00:00:00Z",
            "--data-dir",
            str(db.data_dir),
        ],
    )
    assert result.exit_code == 0
    assert "pass" in result.output.lower()
```

**Step 2: Run test to verify it fails**

Run: `uv run --project packages/evaluation pytest packages/evaluation/tests/test_cutoff_horizon_check.py::test_cutoff_horizon_check_returns_pass_or_fail -v`
Expected: FAIL (CLI option mismatch).

**Step 3: Write minimal implementation**

```python
# evaluation_harness/service.py
from repo_routing.time import parse_dt_utc
from .db import RepoDb


def cutoff_horizon_check(*, repo: str, cutoff: str, data_dir: str = "data") -> dict[str, object]:
    dt = parse_dt_utc(cutoff)
    if dt is None:
        raise ValueError("invalid cutoff")
    db = RepoDb(repo=repo, data_dir=data_dir)
    conn = db.connect()
    try:
        horizon = db.max_event_occurred_at(conn)
    finally:
        conn.close()
    ok = horizon is not None and dt <= horizon
    return {"ok": ok, "cutoff": cutoff, "db_max_event_occurred_at": None if horizon is None else horizon.isoformat()}
```

```python
# evaluation_harness/cli/app.py (replace cutoff command)
@app.command("cutoff")
def cutoff_check(
    repo: str = typer.Option(...),
    cutoff: str = typer.Option(...),
    data_dir: str = typer.Option(DEFAULT_DATA_DIR),
):
    out = cutoff_horizon_check(repo=repo, cutoff=cutoff, data_dir=data_dir)
    typer.echo("pass" if out["ok"] else "fail")
    typer.echo(out)
    if not out["ok"]:
        raise typer.Exit(code=1)
```

**Step 4: Run test to verify it passes**

Run: `uv run --project packages/evaluation pytest packages/evaluation/tests/test_cutoff_horizon_check.py::test_cutoff_horizon_check_returns_pass_or_fail -v`
Expected: PASS.

**Step 5: Commit**

```bash
jj status
jj commit -m "feat(evaluation): add cutoff horizon check CLI"
```

---

### Task 10: Make evaluation per-PR stage artifact-native

**Files:**
- Create: `packages/evaluation/tests/test_runner_per_pr_artifact_native.py`
- Modify: `packages/evaluation/src/evaluation_harness/runner_models.py`
- Modify: `packages/evaluation/src/evaluation_harness/runner_prepare.py`
- Modify: `packages/evaluation/src/evaluation_harness/runner_per_pr.py`

**Step 1: Write the failing test**

```python
import json

from evaluation_harness.config import EvalRunConfig
from evaluation_harness.runner import run_streaming_eval
from repo_routing.registry import RouterSpec

from .fixtures.build_min_db import build_min_db


def test_runner_writes_artifact_index_with_truth_and_routes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)
    cfg = EvalRunConfig(repo=db.repo, data_dir=str(db.data_dir), run_id="artifact-native")
    run_streaming_eval(
        cfg=cfg,
        pr_numbers=[db.pr_number],
        router_specs=[RouterSpec(type="builtin", name="mentions")],
    )

    idx = db.data_dir / "github" / "acme" / "widgets" / "eval" / "artifact-native" / "artifact_index.jsonl"
    rows = [json.loads(line) for line in idx.read_text(encoding="utf-8").splitlines() if line.strip()]
    kinds = {r["artifact_type"] for r in rows}
    assert "route_result" in kinds
    assert "truth_label" in kinds
```

**Step 2: Run test to verify it fails**

Run: `uv run --project packages/evaluation pytest packages/evaluation/tests/test_runner_per_pr_artifact_native.py::test_runner_writes_artifact_index_with_truth_and_routes -v`
Expected: FAIL (`artifact_index.jsonl` missing or missing artifact types).

**Step 3: Write minimal implementation**

```python
# runner_prepare.py
from sdlc_core.store import FileArtifactStore, FileRunStore

artifact_store = FileArtifactStore(root=run_dir)
run_store = FileRunStore(root=run_dir)

# add these to PreparedEvalStage
```

```python
# runner_per_pr.py
# when truth is computed
prepared.artifact_store.write_artifact(record=truth_record, cache_key=f"truth:{prepared.cfg.repo}:{pr_number}:{cutoff.isoformat()}:{policy_id}")

# when route result is computed
prepared.artifact_store.write_artifact(record=route_record, cache_key=f"route:{router_id}:{prepared.cfg.repo}:{pr_number}:{cutoff.isoformat()}")
```

Write artifacts for: `pr_snapshot`, `pr_inputs`, `truth_label`, `gate_metrics`, `route_result`, `routing_metrics`, `queue_metrics`.

**Step 4: Run test to verify it passes**

Run: `uv run --project packages/evaluation pytest packages/evaluation/tests/test_runner_per_pr_artifact_native.py::test_runner_writes_artifact_index_with_truth_and_routes -v`
Expected: PASS.

**Step 5: Commit**

```bash
jj status
jj commit -m "feat(evaluation): make per-pr runner write artifact-native outputs"
```

---

### Task 11: Derive `per_pr.jsonl` and `report.json` from artifact index

**Files:**
- Create: `packages/evaluation/src/evaluation_harness/derived_views.py`
- Create: `packages/evaluation/tests/test_derived_views_v2.py`
- Modify: `packages/evaluation/src/evaluation_harness/runner_emit.py`
- Modify: `packages/evaluation/src/evaluation_harness/runner_aggregate.py`

**Step 1: Write the failing test**

```python
from evaluation_harness.config import EvalRunConfig
from evaluation_harness.runner import run_streaming_eval
from repo_routing.registry import RouterSpec

from .fixtures.build_min_db import build_min_db


def test_emit_materializes_report_and_per_pr_from_artifacts(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)
    cfg = EvalRunConfig(repo=db.repo, data_dir=str(db.data_dir), run_id="derived-v2")
    res = run_streaming_eval(
        cfg=cfg,
        pr_numbers=[db.pr_number],
        router_specs=[RouterSpec(type="builtin", name="mentions")],
    )

    assert (res.run_dir / "per_pr.jsonl").exists()
    assert (res.run_dir / "report.json").exists()
```

**Step 2: Run test to verify it fails**

Run: `uv run --project packages/evaluation pytest packages/evaluation/tests/test_derived_views_v2.py::test_emit_materializes_report_and_per_pr_from_artifacts -v`
Expected: FAIL (derived files missing or incomplete).

**Step 3: Write minimal implementation**

```python
# derived_views.py
from __future__ import annotations

import json
from pathlib import Path


def materialize_per_pr_jsonl(*, run_dir: Path) -> None:
    # read artifact_index.jsonl + artifact payload files
    # group by PR and write compact per_pr rows
    ...


def materialize_report_json(*, run_dir: Path) -> dict[str, object]:
    # aggregate routing metrics from routing_metrics artifacts
    ...
```

```python
# runner_emit.py
from .derived_views import materialize_per_pr_jsonl, materialize_report_json

materialize_per_pr_jsonl(run_dir=prepared.run_dir)
report_payload = materialize_report_json(run_dir=prepared.run_dir)
prepared.store.write_json("report.json", report_payload)
```

**Step 4: Run test to verify it passes**

Run: `uv run --project packages/evaluation pytest packages/evaluation/tests/test_derived_views_v2.py::test_emit_materializes_report_and_per_pr_from_artifacts -v`
Expected: PASS.

**Step 5: Commit**

```bash
jj status
jj commit -m "feat(evaluation): derive per_pr and report views from artifact index"
```

---

### Task 12: Add top-level `repo artifacts list/show` commands

**Files:**
- Create: `packages/cli/tests/test_repo_artifacts_cli.py`
- Create: `packages/evaluation/src/evaluation_harness/artifact_service.py`
- Modify: `packages/cli/src/repo_cli/cli.py`
- Modify: `packages/evaluation/src/evaluation_harness/api.py`

**Step 1: Write the failing test**

```python
from repo_cli.cli import app
from typer.testing import CliRunner


def test_repo_artifacts_group_exists() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["artifacts", "--help"])
    assert result.exit_code == 0, result.output
    assert "list" in result.output
    assert "show" in result.output
```

**Step 2: Run test to verify it fails**

Run: `uv run --project packages/cli pytest packages/cli/tests/test_repo_artifacts_cli.py::test_repo_artifacts_group_exists -v`
Expected: FAIL (`No such command 'artifacts'`).

**Step 3: Write minimal implementation**

```python
# evaluation_harness/artifact_service.py
from __future__ import annotations

import json
from pathlib import Path

from .paths import repo_eval_run_dir


def list_artifacts(*, repo: str, run_id: str, data_dir: str = "data") -> list[dict[str, object]]:
    idx = repo_eval_run_dir(repo_full_name=repo, data_dir=data_dir, run_id=run_id) / "artifact_index.jsonl"
    if not idx.exists():
        return []
    return [json.loads(line) for line in idx.read_text(encoding="utf-8").splitlines() if line.strip()]


def show_artifact(*, repo: str, run_id: str, artifact_id: str, data_dir: str = "data") -> dict[str, object]:
    run_dir = repo_eval_run_dir(repo_full_name=repo, data_dir=data_dir, run_id=run_id)
    rows = list_artifacts(repo=repo, run_id=run_id, data_dir=data_dir)
    row = next((r for r in rows if r.get("artifact_id") == artifact_id), None)
    if row is None:
        raise FileNotFoundError(artifact_id)
    p = run_dir / str(row["relative_path"])
    return json.loads(p.read_text(encoding="utf-8"))
```

```python
# repo_cli/cli.py (add artifacts Typer)
artifacts_app = typer.Typer(add_completion=False)

@artifacts_app.command("list")
def artifacts_list(...):
    ...

@artifacts_app.command("show")
def artifacts_show(...):
    ...

app.add_typer(artifacts_app, name="artifacts")
```

**Step 4: Run test to verify it passes**

Run: `uv run --project packages/cli pytest packages/cli/tests/test_repo_artifacts_cli.py::test_repo_artifacts_group_exists -v`
Expected: PASS.

**Step 5: Commit**

```bash
jj status
jj commit -m "feat(cli): add repo artifacts list/show commands"
```

---

### Task 13: Add candidate/champion registry for promotion

**Files:**
- Create: `packages/experimentation/src/experimentation/workflow_registry.py`
- Create: `packages/experimentation/tests/test_candidate_registry.py`
- Modify: `packages/experimentation/src/experimentation/unified_experiment.py`
- Modify: `packages/experimentation/src/experimentation/workflow_promote.py`

**Step 1: Write the failing test**

```python
from experimentation.workflow_registry import CandidateRegistry


def test_candidate_registry_promotes_champion(tmp_path) -> None:
    reg = CandidateRegistry(root=tmp_path)
    reg.register(task_id="reviewer_routing", candidate_ref="router.llm_rerank@v3")
    reg.promote(task_id="reviewer_routing", candidate_ref="router.llm_rerank@v3")

    state = reg.get(task_id="reviewer_routing")
    assert state["champion"] == "router.llm_rerank@v3"
```

**Step 2: Run test to verify it fails**

Run: `uv run --project packages/experimentation pytest packages/experimentation/tests/test_candidate_registry.py::test_candidate_registry_promotes_champion -v`
Expected: FAIL (`ModuleNotFoundError`).

**Step 3: Write minimal implementation**

```python
# workflow_registry.py
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
        p.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
```

Wire new CLI commands in `unified_experiment.py` (`candidate add`, `candidate list`, `promote`).

**Step 4: Run test to verify it passes**

Run: `uv run --project packages/experimentation pytest packages/experimentation/tests/test_candidate_registry.py::test_candidate_registry_promotes_champion -v`
Expected: PASS.

**Step 5: Commit**

```bash
jj status
jj commit -m "feat(experimentation): add candidate/champion registry"
```

---

### Task 14: Add `repo backfill semantic` cache-first backfill command

**Files:**
- Create: `packages/inference/src/repo_routing/semantic/backfill.py`
- Create: `packages/inference/tests/test_semantic_backfill.py`
- Modify: `packages/inference/src/repo_routing/cli/app.py`
- Modify: `packages/cli/src/repo_cli/cli.py`

**Step 1: Write the failing test**

```python
from repo_cli.cli import app
from typer.testing import CliRunner


def test_repo_backfill_group_exists() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["backfill", "--help"])
    assert result.exit_code == 0, result.output
    assert "semantic" in result.output
```

**Step 2: Run test to verify it fails**

Run: `uv run --project packages/cli pytest packages/cli/tests/test_repo_artifacts_cli.py::test_repo_backfill_group_exists -v`
Expected: FAIL (`No such command 'backfill'`).

**Step 3: Write minimal implementation**

```python
# repo_routing/semantic/backfill.py
from __future__ import annotations


def backfill_semantic_artifacts(*, repo: str, prompt_id: str, since: str, data_dir: str = "data", dry_run: bool = False) -> dict[str, object]:
    # phase-1 minimal: enumerate target PRs, compute semantic cache keys,
    # write only missing artifacts, return counts.
    return {
        "repo": repo,
        "prompt_id": prompt_id,
        "since": since,
        "dry_run": dry_run,
        "would_compute": 0,
        "computed": 0,
        "cache_hits": 0,
    }
```

```python
# repo_cli/cli.py add top-level backfill Typer with semantic subcommand
```

**Step 4: Run test to verify it passes**

Run: `uv run --project packages/cli pytest packages/cli/tests/test_repo_artifacts_cli.py::test_repo_backfill_group_exists -v`
Expected: PASS.

**Step 5: Commit**

```bash
jj status
jj commit -m "feat(cli): add repo backfill semantic command"
```

---

### Task 15: Documentation + end-to-end scenario script

**Files:**
- Create: `docs/quickstart.md`
- Create: `docs/artifact-types-cache-keys.md`
- Create: `scripts/scenario_artifact_native_v2.sh`
- Create: `packages/cli/tests/test_docs_quickstart_v2.py`
- Modify: `docs/README.md`
- Modify: `docs/system-transcript.md`

**Step 1: Write the failing docs test**

```python
from pathlib import Path


def test_quickstart_mentions_artifacts_and_backfill() -> None:
    quickstart = Path("docs/quickstart.md")
    assert quickstart.exists()
    text = quickstart.read_text(encoding="utf-8")
    assert "repo artifacts list" in text
    assert "repo backfill semantic" in text
```

**Step 2: Run test to verify it fails**

Run: `uv run --project packages/cli pytest packages/cli/tests/test_docs_quickstart_v2.py::test_quickstart_mentions_artifacts_and_backfill -v`
Expected: FAIL (`docs/quickstart.md` missing).

**Step 3: Write minimal implementation docs/script**

```markdown
# docs/quickstart.md
# Quickstart (Artifact-Native V2)
1. uv sync
2. repo ingestion ingest --repo owner/name
3. repo evaluation cutoff --repo owner/name --cutoff 2026-01-01T00:00:00Z
4. repo experiment run --spec experiment.json
5. repo artifacts list --repo owner/name --run-id <run_id>
6. repo backfill semantic --repo owner/name --prompt reviewer_rerank --since 2026-01-01T00:00:00Z
```

```bash
# scripts/scenario_artifact_native_v2.sh
#!/usr/bin/env bash
set -euo pipefail
uv run --project packages/cli repo ingestion ingest --repo "$1"
# ... run eval, backfill, compare, promote
```

**Step 4: Run tests + validation**

Run:

```bash
uv run --project packages/cli pytest packages/cli/tests/test_docs_quickstart_v2.py -v
uv run --project packages/core pytest
uv run --project packages/inference pytest
uv run --project packages/evaluation pytest
uv run --project packages/experimentation pytest
uv run --project packages/cli pytest
./scripts/validate_feature_stack.sh
```

Expected: PASS across suites and validation script.

**Step 5: Commit**

```bash
jj status
jj commit -m "docs: add v2 quickstart, cache-key reference, and scenario script"
```

---

## Final verification checklist (must all be true)

- [ ] `repo evaluation cutoff --repo X --cutoff t` returns pass/fail and enforces stale horizon guard.
- [ ] Evaluation run writes `artifact_index.jsonl` and all key artifacts with provenance.
- [ ] Running identical LLM semantic task twice results in cache hits (0 new calls).
- [ ] `repo artifacts list --repo X --run-id R` and `repo artifacts show --artifact <id>` work.
- [ ] `repo backfill semantic ... --dry-run` reports recomputation plan without writing.
- [ ] Candidate/champion registry supports add -> evaluate -> promote.
- [ ] `docs/quickstart.md` can be followed end-to-end on a small repo.

## Notes for execution discipline

- Keep commits tiny; one task == one commit.
- If a task grows beyond 30 minutes, split it into two tasks before coding.
- Do not refactor unrelated modules while touching rewrite code.
- Prefer adding explicit schema/version fields over hidden implicit behavior.
