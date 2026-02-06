from __future__ import annotations

from ...inputs.models import PRInputBundle


def build_interaction_features(
    *,
    input: PRInputBundle,
    pr_features: dict[str, int | float | bool],
    candidate_features: dict[str, dict[str, int | float | bool]],
) -> dict[str, dict[str, int | float | bool]]:
    """Placeholder for PR x candidate interaction features.

    High-level examples:
    - `author_affinity * area_overlap`
    - `request_signal * activity_recency`
    - `owner_match * recent_volume`

    Keep this function deterministic and purely derived from already cutoff-safe
    family feature tables.
    """
    raise NotImplementedError
