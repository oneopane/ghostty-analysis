from __future__ import annotations

from datetime import timedelta

from pydantic import BaseModel, Field


class EvalDefaults(BaseModel):
    """Pinned v0 defaults."""

    strict_streaming_eval: bool = True
    cutoff_policy: str = "created_at"

    truth_window: timedelta = timedelta(minutes=60)
    truth_include_review_comments: bool = True
    truth_policies: tuple[str, ...] = ("first_response_v1", "first_approval_v1")
    truth_primary_policy: str = "first_approval_v1"
    truth_policy_plugins: tuple[str, ...] = ()
    truth_policy_plugin_allowlist: tuple[str, ...] = (
        "evaluation_harness.truth_plugins.",
    )
    llm_mode: str = "replay"

    # Legacy knobs retained during migration (v0 compatibility).
    intent_truth_window: timedelta = timedelta(minutes=60)
    behavior_truth_policy: str = "first_non_author_non_bot_review"
    intent_truth_from_review_requests: bool = False

    exclude_bots: bool = True
    exclude_author: bool = True

    candidate_pool_lookback_days: int = 180

    top_k: int = 5
    hit_ks: tuple[int, ...] = (1, 3, 5)

    def resolved_truth_window(self) -> timedelta:
        """Single source of truth for behavior-truth window during migration."""
        if self.truth_window.total_seconds() > 0:
            return self.truth_window
        return self.intent_truth_window

    def resolved_truth_policy_ids(self) -> tuple[str, ...]:
        # Migrate legacy policy flags into the policy-id path.
        out: list[str] = []
        for item in self.truth_policies:
            pid = str(item).strip()
            if pid and pid not in out:
                out.append(pid)

        if not out:
            if self.behavior_truth_policy == "first_non_author_non_bot_review":
                out.append("first_response_v1")
            else:
                out.append("first_approval_v1")

        if self.intent_truth_from_review_requests and "first_approval_v1" not in out:
            out.append("first_approval_v1")

        return tuple(out)

    def resolved_truth_primary_policy(self) -> str:
        primary = self.truth_primary_policy.strip()
        if primary:
            return primary
        policies = self.resolved_truth_policy_ids()
        return policies[0]


class EvalRunConfig(BaseModel):
    repo: str
    data_dir: str = "data"
    run_id: str

    defaults: EvalDefaults = Field(default_factory=EvalDefaults)
