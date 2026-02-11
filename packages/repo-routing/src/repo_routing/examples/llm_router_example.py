from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ..predictor.base import FeatureExtractor, Ranker
from ..predictor.pipeline import PipelinePredictor
from ..registry import PredictorRouterAdapter
from ..router.base import Evidence, RouteCandidate, RouteResult, Target, TargetType
from ..router.baselines.mentions import extract_targets


class ExampleLLMRouterConfig(BaseModel):
    model_name: str = "dummy-llm-v0"
    mention_boost: float = 2.0
    review_request_boost: float = 1.5
    area_overlap_boost: float = 0.5


class PromptLikeFeatureExtractor(FeatureExtractor):
    def __init__(self, *, model_name: str) -> None:
        self.model_name = model_name

    def extract(self, input) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        text = "\n".join([input.title or "", input.body or ""]).strip()
        prompt_payload = {
            "repo": input.repo,
            "pr_number": input.pr_number,
            "cutoff": input.cutoff.isoformat(),
            "title": input.title,
            "body": input.body,
            "areas": input.areas,
            "review_requests": [
                {"type": rr.reviewer_type, "reviewer": rr.reviewer}
                for rr in input.review_requests
            ],
            "changed_files": [f.path for f in input.changed_files],
            "repo_profile_path": input.repo_profile_path,
            "repo_profile_qa": input.repo_profile_qa,
        }
        prompt_json = json.dumps(
            prompt_payload,
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
        )
        prompt_hash = hashlib.sha256(prompt_json.encode("utf-8")).hexdigest()

        mentions = [t for t in extract_targets(text) if t.type == TargetType.user]
        mention_logins = [t.name for t in mentions]

        requested = [
            rr.reviewer
            for rr in input.review_requests
            if rr.reviewer_type == "user"
        ]

        # Stub for external LLM output: deterministic, bounded payload.
        pseudo_llm_ranked = sorted(set([*requested, *mention_logins]), key=str.lower)

        return {
            "feature_version": "example-v0",
            "model_name": self.model_name,
            "prompt_hash": prompt_hash,
            "prompt_ref": f"llm/{input.repo.replace('/', '_')}/pr-{input.pr_number}/prompt-{prompt_hash[:12]}.json",
            "response_ref": f"llm/{input.repo.replace('/', '_')}/pr-{input.pr_number}/response-{prompt_hash[:12]}.json",
            "mentioned_users": mention_logins,
            "requested_users": requested,
            "pseudo_llm_ranked_users": pseudo_llm_ranked,
            "areas": list(input.areas),
            "repo_profile_path": input.repo_profile_path,
            "repo_profile_codeowners_present": bool(
                ((input.repo_profile_qa or {}).get("coverage") or {}).get(
                    "codeowners_present", False
                )
            ),
            "meta": {
                "candidate_gen_version": "cg.v1",
            },
        }


class FeatureRanker(Ranker):
    def __init__(self, *, cfg: ExampleLLMRouterConfig) -> None:
        self.cfg = cfg

    def rank(self, input, features: dict[str, Any], *, top_k: int) -> RouteResult:  # type: ignore[no-untyped-def]
        scores: dict[str, float] = {}

        for login in features.get("pseudo_llm_ranked_users", []):
            if isinstance(login, str):
                scores[login] = scores.get(login, 0.0) + 1.0

        for login in features.get("mentioned_users", []):
            if isinstance(login, str):
                scores[login] = scores.get(login, 0.0) + self.cfg.mention_boost

        for login in features.get("requested_users", []):
            if isinstance(login, str):
                scores[login] = scores.get(login, 0.0) + self.cfg.review_request_boost

        if input.author_login and input.author_login in scores:
            scores[input.author_login] = 0.0

        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0].lower()))

        candidates: list[RouteCandidate] = []
        for login, score in ranked[:top_k]:
            candidates.append(
                RouteCandidate(
                    target=Target(type=TargetType.user, name=login),
                    score=float(score),
                    evidence=[
                        Evidence(
                            kind="llm_features",
                            data={
                                "model_name": features.get("model_name"),
                                "feature_version": features.get("feature_version"),
                                "prompt_hash": features.get("prompt_hash"),
                                "prompt_ref": features.get("prompt_ref"),
                                "response_ref": features.get("response_ref"),
                            },
                        )
                    ],
                )
            )

        return RouteResult(
            repo=input.repo,
            pr_number=input.pr_number,
            as_of=input.cutoff,
            top_k=top_k,
            candidates=candidates,
            risk="low" if candidates else "high",
            confidence="medium" if candidates else "low",
            notes=["example import-path llm-style router"],
        )


def create_router(config_path: str | None = None):  # type: ignore[no-untyped-def]
    cfg = ExampleLLMRouterConfig()
    if config_path is not None:
        p = Path(config_path)
        if p.exists():
            cfg = ExampleLLMRouterConfig.model_validate_json(p.read_text(encoding="utf-8"))

    predictor = PipelinePredictor(
        feature_extractor=PromptLikeFeatureExtractor(model_name=cfg.model_name),
        ranker=FeatureRanker(cfg=cfg),
    )
    return PredictorRouterAdapter(predictor=predictor)
