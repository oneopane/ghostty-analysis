from __future__ import annotations

import hashlib
import importlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TruthTargetKind(StrEnum):
    actor_set = "actor_set"


class TruthSelector(StrEnum):
    first = "first"
    last = "last"
    union = "union"
    priority_chain = "priority_chain"


class TruthSource(StrEnum):
    reviews = "reviews"
    review_comments = "review_comments"
    events = "events"
    review_requests = "review_requests"


class TruthPolicySpec(BaseModel):
    id: str
    version: str = "v1"
    target_kind: TruthTargetKind = TruthTargetKind.actor_set
    window_seconds: int = 3600
    sources: list[TruthSource] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    selector: TruthSelector = TruthSelector.first
    status_rules: list[dict[str, Any]] = Field(default_factory=list)
    fallback_chain: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        out = value.strip()
        if not out:
            raise ValueError("policy id is required")
        if not re.fullmatch(r"[a-z0-9_]+", out):
            raise ValueError("policy id must match [a-z0-9_]+")
        return out

    @field_validator("window_seconds")
    @classmethod
    def _validate_window(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("window_seconds must be > 0")
        return value

    def stable_hash(self) -> str:
        payload = self.model_dump(mode="json")
        data = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        return hashlib.sha256(data.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ResolvedTruthPolicy:
    spec: TruthPolicySpec
    source: str
    source_ref: str
    policy_hash: str


def builtin_truth_policy_specs() -> dict[str, TruthPolicySpec]:
    """Narrow v1 built-ins used by evaluation truth contracts."""
    specs = [
        TruthPolicySpec(
            id="first_response_v1",
            window_seconds=3600,
            sources=[TruthSource.reviews, TruthSource.review_comments],
            filters={"exclude_bots": True, "exclude_author": True},
            selector=TruthSelector.first,
            status_rules=[
                {"if": "target_found", "status": "observed"},
                {"if": "coverage_complete", "status": "no_post_cutoff_response"},
                {"if": "default", "status": "unknown_due_to_ingestion_gap"},
            ],
        ),
        TruthPolicySpec(
            id="first_approval_v1",
            window_seconds=3600,
            sources=[TruthSource.reviews],
            filters={
                "exclude_bots": True,
                "exclude_author": True,
                "review_states": ["APPROVED"],
            },
            selector=TruthSelector.first,
            status_rules=[
                {"if": "target_found", "status": "observed"},
                {"if": "coverage_complete", "status": "no_post_cutoff_response"},
                {"if": "default", "status": "unknown_due_to_ingestion_gap"},
            ],
        ),
        TruthPolicySpec(
            id="merger_v1",
            window_seconds=48 * 3600,
            sources=[TruthSource.events],
            filters={"event_types": ["pull_request.merged"]},
            selector=TruthSelector.first,
            status_rules=[
                {"if": "target_found", "status": "observed"},
                {"if": "policy_not_ready", "status": "policy_unavailable"},
                {"if": "default", "status": "no_post_cutoff_response"},
            ],
        ),
        TruthPolicySpec(
            id="hybrid_owner_v1",
            window_seconds=48 * 3600,
            sources=[TruthSource.reviews, TruthSource.events, TruthSource.review_requests],
            filters={"exclude_bots": True, "exclude_author": True},
            selector=TruthSelector.priority_chain,
            status_rules=[
                {"if": "approval_branch", "status": "observed"},
                {"if": "merger_branch", "status": "observed"},
                {"if": "request_branch", "status": "observed"},
                {"if": "coverage_complete", "status": "no_post_cutoff_response"},
                {"if": "default", "status": "unknown_due_to_ingestion_gap"},
            ],
            fallback_chain=["first_approval_v1", "merger_v1", "first_response_v1"],
        ),
    ]
    return {spec.id: spec for spec in specs}


def _is_allowed_import(import_path: str, allowlist_prefixes: tuple[str, ...]) -> bool:
    if not allowlist_prefixes:
        return False
    return any(import_path.startswith(prefix) for prefix in allowlist_prefixes)


def _load_import_target(import_path: str):  # type: ignore[no-untyped-def]
    if ":" not in import_path:
        raise ValueError(
            f"invalid truth policy import path (expected module:attr): {import_path}"
        )
    module_name, attr_name = import_path.split(":", 1)
    mod = importlib.import_module(module_name)
    try:
        return getattr(mod, attr_name)
    except AttributeError as exc:
        raise ValueError(f"missing truth policy attribute: {import_path}") from exc


def _coerce_loaded_policy(obj: object, *, import_path: str) -> TruthPolicySpec:
    if isinstance(obj, TruthPolicySpec):
        return obj
    if isinstance(obj, dict):
        return TruthPolicySpec.model_validate(obj)
    raise TypeError(
        f"truth policy plugin {import_path} must return TruthPolicySpec or dict"
    )


def load_plugin_truth_policies(
    *,
    import_paths: tuple[str, ...],
    allowlist_prefixes: tuple[str, ...],
) -> dict[str, ResolvedTruthPolicy]:
    out: dict[str, ResolvedTruthPolicy] = {}
    for import_path in import_paths:
        normalized = import_path.strip()
        if not normalized:
            continue
        if not _is_allowed_import(normalized, allowlist_prefixes):
            raise ValueError(
                f"truth policy import path not allowlisted: {normalized}"
            )
        target = _load_import_target(normalized)
        loaded = target() if callable(target) else target
        spec = _coerce_loaded_policy(loaded, import_path=normalized)
        if spec.id in out:
            raise ValueError(f"duplicate truth policy id from plugins: {spec.id}")
        out[spec.id] = ResolvedTruthPolicy(
            spec=spec,
            source="plugin",
            source_ref=normalized,
            policy_hash=spec.stable_hash(),
        )
    return out


def resolve_truth_policies(
    *,
    policy_ids: tuple[str, ...],
    plugin_import_paths: tuple[str, ...],
    plugin_allowlist_prefixes: tuple[str, ...],
) -> dict[str, ResolvedTruthPolicy]:
    builtins = builtin_truth_policy_specs()
    plugins = load_plugin_truth_policies(
        import_paths=plugin_import_paths,
        allowlist_prefixes=plugin_allowlist_prefixes,
    )

    catalog: dict[str, ResolvedTruthPolicy] = {
        pid: ResolvedTruthPolicy(
            spec=spec,
            source="builtin",
            source_ref=pid,
            policy_hash=spec.stable_hash(),
        )
        for pid, spec in builtins.items()
    }
    for pid, resolved in plugins.items():
        if pid in catalog:
            raise ValueError(f"plugin policy id collides with builtin policy: {pid}")
        catalog[pid] = resolved

    requested = tuple(pid.strip() for pid in policy_ids if pid.strip())
    if not requested:
        requested = ("first_response_v1",)

    missing = [pid for pid in requested if pid not in catalog]
    if missing:
        raise ValueError(
            "unknown truth policy ids: " + ", ".join(sorted(set(missing), key=str.lower))
        )

    resolved: dict[str, ResolvedTruthPolicy] = {}
    for pid in requested:
        resolved[pid] = catalog[pid]
    return resolved
