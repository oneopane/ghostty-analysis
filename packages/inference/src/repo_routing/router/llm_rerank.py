from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .base import Evidence, RouteCandidate, RouteResult, TargetType
from .baselines.union import UnionRouter
from .llm_cache import LLMReplayCache
from .llm_schema import LLMRerankResponse

if TYPE_CHECKING:
    from ..inputs.models import PRInputBundle


def _stable_hash(payload: dict[str, object]) -> str:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class LLMRerankRouter:
    """Constrained reranker over union candidates with replay support."""

    def __init__(
        self,
        *,
        mode: str = "replay",
        model_name: str = "dummy-llm-v1",
        cache_dir: str | Path = ".cache/inference/llm-replay",
        union_router: UnionRouter | None = None,
        cache: LLMReplayCache | None = None,
    ) -> None:
        normalized_mode = mode.strip().lower()
        if normalized_mode not in {"off", "live", "replay"}:
            raise ValueError(f"invalid llm mode: {mode}")
        self.mode = normalized_mode
        self.model_name = model_name
        self.union_router = union_router or UnionRouter()
        self.cache = cache or LLMReplayCache(cache_dir=cache_dir)
        self.last_llm_steps: dict[str, dict[str, object]] = {}
        self.last_provenance: dict[str, object] = {}

    def _request_payload(
        self, *, repo: str, pr_number: int, as_of: datetime, candidates: list[RouteCandidate]
    ) -> dict[str, object]:
        return {
            "repo": repo,
            "pr_number": pr_number,
            "as_of": as_of.isoformat(),
            "model": self.model_name,
            "candidates": [
                {
                    "target_type": c.target.type.value,
                    "target_name": c.target.name,
                    "score": c.score,
                    "evidence": [e.model_dump(mode="json") for e in c.evidence],
                }
                for c in candidates
            ],
        }

    def _live_response(self, payload: dict[str, object]) -> dict[str, object]:
        raw_candidates = payload.get("candidates")
        candidates = raw_candidates if isinstance(raw_candidates, list) else []
        items: list[dict[str, object]] = []
        for c in candidates:
            if not isinstance(c, dict):
                continue
            target_type = str(c.get("target_type") or "")
            target_name = str(c.get("target_name") or "")
            if target_type not in {TargetType.user.value, TargetType.team.value}:
                continue
            if not target_name:
                continue
            items.append(
                {
                    "target_type": target_type,
                    "target_name": target_name,
                    "score": float(c.get("score") or 0.0),
                    "evidence_refs": [f"candidate:{target_type}:{target_name.lower()}"],
                }
            )
        items.sort(key=lambda i: (-float(i["score"]), str(i["target_name"]).lower()))
        return {
            "model": self.model_name,
            "items": items,
            "latency_ms": 1.0,
            "cost_usd": 0.0,
        }

    def route(
        self,
        *,
        repo: str,
        pr_number: int,
        as_of: datetime,
        data_dir: str = "data",
        top_k: int = 5,
        input_bundle: PRInputBundle | None = None,
    ) -> RouteResult:
        self.last_llm_steps = {}
        self.last_provenance = {}

        union_result = self.union_router.route(
            repo=repo,
            pr_number=pr_number,
            as_of=as_of,
            data_dir=data_dir,
            top_k=max(top_k, 10),
            input_bundle=input_bundle,
        )
        if self.mode == "off":
            return union_result.model_copy(
                update={
                    "notes": [*union_result.notes, "llm_mode=off", "llm_rerank_skipped"],
                }
            )

        request_payload = self._request_payload(
            repo=repo,
            pr_number=pr_number,
            as_of=as_of,
            candidates=list(union_result.candidates),
        )
        request_hash = _stable_hash(request_payload)
        cached = self.cache.get(request_hash)
        if cached is None and self.mode == "replay":
            return union_result.model_copy(
                update={
                    "notes": [
                        *union_result.notes,
                        "llm_mode=replay",
                        "llm_replay_miss",
                    ]
                }
            )

        if cached is None:
            response_payload = self._live_response(request_payload)
            self.cache.put(request_hash, response_payload)
            cache_status = "live_write"
        else:
            response_payload = cached
            cache_status = "replay_hit"

        response = LLMRerankResponse.model_validate(response_payload)
        response_hash = _stable_hash(response.model_dump(mode="json"))
        by_key: dict[tuple[str, str], RouteCandidate] = {
            (c.target.type.value, c.target.name.lower()): c for c in union_result.candidates
        }

        reranked: list[RouteCandidate] = []
        for item in response.items:
            key = (item.target_type, item.target_name.lower())
            base = by_key.get(key)
            if base is None:
                continue
            reranked.append(
                RouteCandidate(
                    target=base.target,
                    score=float(item.score),
                    evidence=[
                        *base.evidence,
                        Evidence(
                            kind="llm_rerank",
                            data={
                                "model": response.model,
                                "request_hash": request_hash,
                                "response_hash": response_hash,
                                "evidence_refs": list(item.evidence_refs),
                            },
                        ),
                    ],
                )
            )
        reranked.sort(key=lambda c: (-c.score, c.target.name.lower()))

        self.last_llm_steps = {
            "request": request_payload,
            "response": response.model_dump(mode="json"),
            "cache": {
                "status": cache_status,
                "request_hash": request_hash,
                "response_hash": response_hash,
            },
        }
        self.last_provenance = {
            "router_version": "llm_rerank_v1",
            "mode": self.mode,
            "model": response.model,
            "request_hash": request_hash,
            "response_hash": response_hash,
            "cache_status": cache_status,
            "latency_ms": response.latency_ms,
            "cost_usd": response.cost_usd,
        }

        if not reranked:
            return union_result.model_copy(
                update={
                    "notes": [*union_result.notes, f"llm_mode={self.mode}", "llm_empty_response"]
                }
            )

        return RouteResult(
            repo=repo,
            pr_number=pr_number,
            as_of=as_of,
            top_k=top_k,
            candidates=reranked[:top_k],
            risk=union_result.risk,
            confidence="medium",
            notes=[*union_result.notes, f"llm_mode={self.mode}", f"llm_model={response.model}"],
        )
