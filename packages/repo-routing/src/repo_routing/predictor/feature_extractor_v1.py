from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..inputs.models import PRInputBundle
from .base import FeatureExtractor
from .features.candidate_activity import build_candidate_activity_table
from .features.interaction import build_interaction_features
from .features.ownership import (
    load_codeowners_text_for_pr,
    match_codeowners_for_changed_files,
    parse_codeowners_rules,
)
from .features.ownership import build_ownership_features
from .features.pr_surface import build_pr_surface_features
from .features.pr_timeline import build_pr_timeline_features
from .features.schemas import FeatureExtractionConfig


class AttentionRoutingFeatureExtractorV1(FeatureExtractor):
    """Feature extractor that composes core feature families."""

    def __init__(self, *, config: FeatureExtractionConfig | None = None) -> None:
        self.config = config or FeatureExtractionConfig()

    def extract(self, input: PRInputBundle) -> dict[str, Any]:
        pr_features: dict[str, Any] = {}
        pr_features.update(build_pr_surface_features(input))

        codeowner_logins: set[str] = set()
        if self.config.include_ownership_features:
            ownership = build_ownership_features(
                input,
                data_dir=self.config.data_dir,
                active_candidates=set(),
            )
            pr_features.update(ownership)

            text = load_codeowners_text_for_pr(input=input, data_dir=self.config.data_dir)
            if text:
                rules = parse_codeowners_rules(text)
                summary = match_codeowners_for_changed_files(input, rules=rules)
                codeowner_logins = set(summary.owner_set)

        if self.config.include_pr_timeline_features:
            pr_features.update(
                build_pr_timeline_features(
                    input,
                    data_dir=str(self.config.data_dir),
                    codeowner_logins=codeowner_logins,
                )
            )

        candidate_logins = self._candidate_pool(input, codeowner_logins=codeowner_logins)

        candidates: dict[str, dict[str, Any]] = {}
        if self.config.include_candidate_features and candidate_logins:
            candidates = build_candidate_activity_table(
                input=input,
                candidate_logins=candidate_logins,
                data_dir=self.config.data_dir,
                windows_days=self.config.candidate_windows_days,
            )

        interactions = build_interaction_features(
            input=input,
            pr_features=pr_features,
            candidate_features=candidates,
        )

        return {
            "feature_version": self.config.feature_version,
            "repo": input.repo,
            "pr_number": input.pr_number,
            "cutoff": input.cutoff.isoformat(),
            "pr": pr_features,
            "candidates": candidates,
            "interactions": interactions,
            "meta": {
                "candidate_pool_size": len(candidate_logins),
                "candidate_windows_days": list(self.config.candidate_windows_days),
                "include_pr_timeline_features": self.config.include_pr_timeline_features,
                "include_ownership_features": self.config.include_ownership_features,
                "include_candidate_features": self.config.include_candidate_features,
            },
        }

    def _candidate_pool(
        self,
        input: PRInputBundle,
        *,
        codeowner_logins: set[str],
    ) -> list[str]:
        requested_users = {
            rr.reviewer
            for rr in input.review_requests
            if rr.reviewer_type.lower() == "user"
        }
        mentions = {
            m.group("user")
            for m in _USER_MENTION_RE.finditer("\n".join([input.title or "", input.body or ""]))
        }
        recent = {e.actor_login for e in input.recent_activity}

        pool = set(requested_users) | set(mentions) | set(recent) | set(codeowner_logins)
        if input.author_login:
            pool.discard(input.author_login)

        return sorted(pool, key=lambda s: s.lower())


def build_feature_extractor_v1(
    *,
    data_dir: str | Path = "data",
    include_pr_timeline_features: bool = True,
    include_ownership_features: bool = True,
    include_candidate_features: bool = True,
) -> AttentionRoutingFeatureExtractorV1:
    """Factory helper for router construction and import-path loaders."""
    cfg = FeatureExtractionConfig(
        data_dir=data_dir,
        include_pr_timeline_features=include_pr_timeline_features,
        include_ownership_features=include_ownership_features,
        include_candidate_features=include_candidate_features,
    )
    return AttentionRoutingFeatureExtractorV1(config=cfg)


_USER_MENTION_RE = re.compile(
    r"(?<![A-Za-z0-9_])@(?P<user>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))"
)
