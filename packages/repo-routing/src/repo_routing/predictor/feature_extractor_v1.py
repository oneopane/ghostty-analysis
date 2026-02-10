from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from ..inputs.models import PRInputBundle
from .base import FeatureExtractor
from .features.candidate_activity import build_candidate_activity_table
from .features.feature_registry import DEFAULT_FEATURE_REGISTRY, flatten_extracted_feature_keys
from .features.task_policy import DEFAULT_TASK_POLICY_REGISTRY
from .features.interaction import build_interaction_features
from .features.team_roster import expand_team_members, load_team_roster
from .features.ownership import (
    load_codeowners_text_for_pr,
    match_codeowners_for_changed_files,
    parse_codeowners_rules,
)
from .features.automation import build_automation_features
from .features.ownership import build_ownership_features
from .features.pr_surface import build_pr_surface_features
from .features.pr_timeline import build_pr_timeline_features
from .features.repo_priors import build_repo_priors_features
from .features.schemas import FeatureExtractionConfig
from .features.similarity import build_similarity_features


class AttentionRoutingFeatureExtractorV1(FeatureExtractor):
    """Feature extractor that composes core feature families."""

    def __init__(self, *, config: FeatureExtractionConfig | None = None) -> None:
        self.config = config or FeatureExtractionConfig()

    def extract(self, input: PRInputBundle) -> dict[str, Any]:
        pr_features: dict[str, Any] = {}
        pr_features.update(build_pr_surface_features(input))

        codeowner_logins: set[str] = set()
        source_hashes: dict[str, str] = {}
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
                source_hashes["codeowners"] = hashlib.sha256(text.encode("utf-8")).hexdigest()

            overrides_path = self._repo_overrides_path(input.repo)
            if overrides_path.exists():
                source_hashes["area_overrides"] = hashlib.sha256(
                    overrides_path.read_bytes()
                ).hexdigest()

        if self.config.include_pr_timeline_features:
            pr_features.update(
                build_pr_timeline_features(
                    input,
                    data_dir=str(self.config.data_dir),
                    codeowner_logins=codeowner_logins,
                )
            )

        try:
            pr_features.update(
                build_repo_priors_features(
                    input=input,
                    data_dir=self.config.data_dir,
                )
            )
        except Exception:
            pass
        try:
            pr_features.update(
                build_similarity_features(
                    input=input,
                    data_dir=self.config.data_dir,
                )
            )
        except Exception:
            pass
        try:
            pr_features.update(
                build_automation_features(
                    input=input,
                    data_dir=self.config.data_dir,
                )
            )
        except Exception:
            pass

        # Cross-family silence feature (automation channel absent at cutoff).
        pr_features["pr.silence.no_automation_feedback_pre_cutoff"] = (
            int(pr_features.get("automation.bot_comment_count", 0) or 0) == 0
        )

        candidate_logins, candidate_teams = self._candidate_pool(input, codeowner_logins=codeowner_logins)

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
            data_dir=str(self.config.data_dir),
        )

        out = {
            "feature_version": self.config.feature_version,
            "repo": input.repo,
            "pr_number": input.pr_number,
            "cutoff": input.cutoff.isoformat(),
            "pr": {k: pr_features[k] for k in sorted(pr_features)},
            "candidates": {k: candidates[k] for k in sorted(candidates, key=str.lower)},
            "interactions": {k: interactions[k] for k in sorted(interactions, key=str.lower)},
            "meta": {
                "candidate_pool_size": len(candidate_logins),
                "candidate_pool_users_count": len(candidate_logins),
                "candidate_pool_teams_count": len(candidate_teams),
                "candidate_windows_days": list(self.config.candidate_windows_days),
                "include_pr_timeline_features": self.config.include_pr_timeline_features,
                "include_ownership_features": self.config.include_ownership_features,
                "include_candidate_features": self.config.include_candidate_features,
                "candidate_logins": candidate_logins,
                "candidate_teams": candidate_teams,
                "candidate_gen_version": self.config.candidate_gen_version,
            },
            "labels": {
                "labels.truth_first_responder": None,
                "labels.truth_in_candidate_pool": None,
                "labels.missed_by_candidate_gen": None,
            },
            "debug": {
                "feature_version": self.config.feature_version,
                "candidate_gen_version": self.config.candidate_gen_version,
                "owner_definition_version": self.config.ownership_version,
                "similarity_version": self.config.similarity_version,
                "trajectory_version": self.config.trajectory_version,
                "affinity_version": self.config.affinity_version,
                "priors_version": self.config.priors_version,
                "automation_version": self.config.automation_version,
                "source_hashes": {k: source_hashes[k] for k in sorted(source_hashes)},
            },
        }

        keys = flatten_extracted_feature_keys(out)
        out["meta"]["feature_registry"] = DEFAULT_FEATURE_REGISTRY.coverage(keys)
        if self.config.task_id:
            out["meta"]["task_policy"] = DEFAULT_TASK_POLICY_REGISTRY.evaluate(
                task_id=self.config.task_id,
                feature_keys=keys,
                feature_registry=DEFAULT_FEATURE_REGISTRY,
            )

        return out

    def _repo_overrides_path(self, repo: str) -> Path:
        owner, name = repo.split("/", 1)
        return Path(self.config.data_dir) / "github" / owner / name / "routing" / "area_overrides.json"

    def _candidate_pool(
        self,
        input: PRInputBundle,
        *,
        codeowner_logins: set[str],
    ) -> tuple[list[str], list[str]]:
        requested_users = {
            rr.reviewer
            for rr in input.review_requests
            if rr.reviewer_type.lower() == "user"
        }
        requested_teams = {
            rr.reviewer
            for rr in input.review_requests
            if rr.reviewer_type.lower() == "team"
        }
        mentions = {
            m.group("user")
            for m in _USER_MENTION_RE.finditer("\n".join([input.title or "", input.body or ""]))
        }
        recent = {e.actor_login for e in input.recent_activity}

        owner_users = {x for x in codeowner_logins if not _looks_like_team_ref(x)}
        owner_teams = {x for x in codeowner_logins if _looks_like_team_ref(x)}

        team_pool = set(requested_teams) | set(owner_teams)

        roster = load_team_roster(repo=input.repo, data_dir=self.config.data_dir)
        expanded_team_users = expand_team_members(team_names=team_pool, roster=roster)

        pool = (
            set(requested_users)
            | set(mentions)
            | set(recent)
            | set(owner_users)
            | set(expanded_team_users)
        )
        if input.author_login:
            pool.discard(input.author_login)

        return (
            sorted(pool, key=lambda s: s.lower()),
            sorted(team_pool, key=lambda s: s.lower()),
        )


def build_feature_extractor_v1(
    *,
    data_dir: str | Path = "data",
    include_pr_timeline_features: bool = True,
    include_ownership_features: bool = True,
    include_candidate_features: bool = True,
    task_id: str | None = None,
) -> AttentionRoutingFeatureExtractorV1:
    """Factory helper for router construction and import-path loaders."""
    cfg = FeatureExtractionConfig(
        data_dir=data_dir,
        include_pr_timeline_features=include_pr_timeline_features,
        include_ownership_features=include_ownership_features,
        include_candidate_features=include_candidate_features,
        task_id=task_id,
    )
    return AttentionRoutingFeatureExtractorV1(config=cfg)


def _looks_like_team_ref(value: str) -> bool:
    v = value.strip().lower()
    return v.startswith("team:") or "/" in v


_USER_MENTION_RE = re.compile(
    r"(?<![A-Za-z0-9_])@(?P<user>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))"
)
