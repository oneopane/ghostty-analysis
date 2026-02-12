from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .feature_registry import FeatureRegistry, FeatureSpec


@dataclass(frozen=True)
class TaskPolicySpec:
    task_id: str
    name: str
    allowed_roles: set[str]
    allowed_granularities: set[str]
    allowed_prefixes: tuple[str, ...]
    recommended_model: str
    notes: str = ""


class TaskPolicyRegistry:
    def __init__(self, *, version: str = "tp.v1") -> None:
        self.version = version
        self._policies: dict[str, TaskPolicySpec] = {}

    def register(self, policy: TaskPolicySpec) -> None:
        self._policies[policy.task_id] = policy

    def get(self, task_id: str) -> TaskPolicySpec | None:
        return self._policies.get(task_id)

    def list_ids(self) -> list[str]:
        return sorted(self._policies)

    def evaluate(
        self,
        *,
        task_id: str,
        feature_keys: list[str],
        feature_registry: FeatureRegistry,
    ) -> dict[str, Any]:
        policy = self.get(task_id)
        if policy is None:
            raise KeyError(f"unknown task policy: {task_id}")

        violations: dict[str, dict[str, str | None]] = {}
        unresolved: list[str] = []

        for k in sorted(set(feature_keys)):
            spec = feature_registry.resolve(k)
            if spec is None:
                unresolved.append(k)
                continue

            reason: str | None = None
            if policy.allowed_prefixes and not any(k.startswith(p) for p in policy.allowed_prefixes):
                reason = "prefix_not_allowed"
            elif spec.role not in policy.allowed_roles:
                reason = "role_not_allowed"
            elif spec.granularity not in policy.allowed_granularities:
                reason = "granularity_not_allowed"

            if reason is not None:
                violations[k] = {
                    "reason": reason,
                    "role": spec.role,
                    "granularity": spec.granularity,
                }

        return {
            "task_policy_version": self.version,
            "task_id": policy.task_id,
            "task_name": policy.name,
            "recommended_model": policy.recommended_model,
            "feature_count": len(set(feature_keys)),
            "unresolved_count": len(unresolved),
            "unresolved_keys": unresolved,
            "violation_count": len(violations),
            "violations": {k: violations[k] for k in sorted(violations)},
        }


def default_task_policy_registry() -> TaskPolicyRegistry:
    r = TaskPolicyRegistry(version="tp.v1")

    # T02 readiness classification (PR-level only; gate/context/calibration)
    r.register(
        TaskPolicySpec(
            task_id="T02",
            name="review_readiness",
            allowed_roles={"gate", "context", "calibration"},
            allowed_granularities={"pr", "set"},
            allowed_prefixes=("pr.", "repo.priors.", "automation."),
            recommended_model="logistic_regression",
            notes="Readiness should not consume pair/candidate ranking signals.",
        )
    )

    # T04 owner coverage confidence
    r.register(
        TaskPolicySpec(
            task_id="T04",
            name="owner_coverage_confidence",
            allowed_roles={"context", "calibration", "gate"},
            allowed_granularities={"pr", "set"},
            allowed_prefixes=("pr.ownership.", "pr.areas.", "pr.surface.", "repo.priors."),
            recommended_model="logistic_regression",
            notes="Center around coverage and dispersion metrics.",
        )
    )

    # T06 first responder routing (pair ranking)
    r.register(
        TaskPolicySpec(
            task_id="T06",
            name="first_responder_routing",
            allowed_roles={"ranking", "context", "calibration"},
            allowed_granularities={"pair", "candidate", "pr", "set"},
            allowed_prefixes=(
                "pair.",
                "candidate.",
                "pr.areas.",
                "pr.surface.",
                "pr.request_overlap.",
                "pr.attention.",
                "repo.priors.",
                "sim.",
            ),
            recommended_model="linear_ranker",
            notes="Core route score should come from pair features; PR-level context may modulate.",
        )
    )

    # T09 stall risk
    r.register(
        TaskPolicySpec(
            task_id="T09",
            name="stall_risk",
            allowed_roles={"calibration", "context", "gate"},
            allowed_granularities={"pr", "candidate", "pair", "set"},
            allowed_prefixes=("pr.", "candidate.", "pair.availability.", "repo.priors.", "automation."),
            recommended_model="calibrated_logistic_regression",
            notes="Probability quality matters more than raw ranking quality.",
        )
    )

    # T10 reviewer set sizing
    r.register(
        TaskPolicySpec(
            task_id="T10",
            name="reviewer_set_sizing",
            allowed_roles={"calibration", "context"},
            allowed_granularities={"pair", "pr", "candidate", "set"},
            allowed_prefixes=("pair.availability.", "pr.", "candidate.", "repo.priors."),
            recommended_model="deterministic_composition",
            notes="Use calibrated non-response probabilities and closed-form success@k composition.",
        )
    )

    return r


DEFAULT_TASK_POLICY_REGISTRY = default_task_policy_registry()
