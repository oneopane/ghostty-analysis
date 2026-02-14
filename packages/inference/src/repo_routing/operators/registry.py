from __future__ import annotations

from repo_routing.registry import builtin_router_names


def list_operator_ids(*, task_id: str) -> list[str]:
    if task_id != "reviewer_routing":
        return []
    return [f"router.{name}" for name in builtin_router_names()]
