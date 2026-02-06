from __future__ import annotations

from ...inputs.models import PRInputBundle


def build_interaction_features(
    *,
    input: PRInputBundle,
    pr_features: dict[str, int | float | bool],
    candidate_features: dict[str, dict[str, int | float | bool]],
) -> dict[str, dict[str, int | float | bool]]:
    """Build simple deterministic PR x candidate interaction features.

    This intentionally starts minimal and can be expanded with richer crosses.
    """

    mention_text = "\n".join([input.title or "", input.body or ""]).lower()
    out: dict[str, dict[str, int | float | bool]] = {}

    is_multi_area = bool(pr_features.get("pr.areas.is_multi", False))
    total_churn = float(pr_features.get("pr.churn.total", 0.0) or 0.0)

    for login in sorted(candidate_features.keys(), key=lambda s: s.lower()):
        cand = candidate_features[login]
        events_30d = float(cand.get("cand.activity.events_30d", 0.0) or 0.0)
        mentioned = f"@{login.lower()}" in mention_text

        out[login] = {
            "x.mentioned_in_pr": mentioned,
            "x.multi_area_and_recent_activity": bool(is_multi_area and events_30d > 0.0),
            "x.churn_times_recent_activity": total_churn * events_30d,
        }

    return out
