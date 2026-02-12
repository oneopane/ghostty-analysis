from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import re
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .inputs.builder import build_pr_input_bundle
from .inputs.models import PRInputBuilderOptions, PRInputBundle
from .predictor.base import Predictor
from .predictor.pipeline import PipelinePredictor
from .router.base import Router
from .router.baselines.codeowners import CodeownersRouter
from .router.baselines.mentions import MentionsRouter
from .router.baselines.popularity import PopularityRouter
from .router.baselines.union import UnionRouter
from .router.hybrid_ranker import HybridRankerRouter
from .router.llm_rerank import LLMRerankRouter
from .router.stewards import StewardsRouter
from .scoring.config import load_scoring_config


class RouterSpec(BaseModel):
    type: str
    name: str
    import_path: str | None = None
    config_path: str | None = None


class HybridRankerConfigPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weights: dict[str, float] = Field(default_factory=dict)


class LLMRerankConfigPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "replay"
    model_name: str = "dummy-llm-v1"
    cache_dir: str = ".cache/inference/llm-replay"

    @field_validator("mode")
    @classmethod
    def _normalize_mode(cls, value: str) -> str:
        mode = str(value).strip().lower()
        if mode not in {"off", "live", "replay"}:
            raise ValueError("mode must be one of: off, live, replay")
        return mode

    @field_validator("model_name")
    @classmethod
    def _normalize_model_name(cls, value: str) -> str:
        return str(value).strip() or "dummy-llm-v1"

    @field_validator("cache_dir")
    @classmethod
    def _normalize_cache_dir(cls, value: str) -> str:
        return str(value).strip() or ".cache/inference/llm-replay"


BuiltinRouterFactory = Callable[[str | None], Router]

_BUILTIN_ROUTER_FACTORIES: dict[str, BuiltinRouterFactory] = {}


def _config_hash(config_path: str | None) -> str:
    if not config_path:
        return "nocfg"
    p = Path(config_path)
    if not p.exists():
        return "missing"
    payload = p.read_bytes()
    return hashlib.sha256(payload).hexdigest()[:10]


def router_id_for_spec(spec: RouterSpec) -> str:
    if spec.type == "builtin":
        return spec.name.strip().lower()
    source = spec.import_path or spec.name
    slug = re.sub(r"[^a-z0-9]+", "-", source.lower()).strip("-")
    short = hashlib.sha256(
        f"{source}|{_config_hash(spec.config_path)}".encode("utf-8")
    ).hexdigest()[:8]
    return f"{slug}-{short}"


def builtin_router_names() -> tuple[str, ...]:
    return tuple(sorted(_BUILTIN_ROUTER_FACTORIES))


def register_builtin_router(name: str, factory: BuiltinRouterFactory) -> None:
    key = name.strip().lower()
    if not key:
        raise ValueError("builtin router name cannot be empty")
    _BUILTIN_ROUTER_FACTORIES[key] = factory


class PredictorRouterAdapter:
    def __init__(
        self,
        *,
        predictor: Predictor,
        input_options: PRInputBuilderOptions | None = None,
    ) -> None:
        self.predictor = predictor
        self.input_options = input_options or PRInputBuilderOptions()

    def route(
        self,
        *,
        repo: str,
        pr_number: int,
        as_of,
        data_dir: str = "data",
        top_k: int = 5,
        input_bundle: PRInputBundle | None = None,
    ):
        bundle = input_bundle
        if bundle is None:
            bundle = build_pr_input_bundle(
                repo=repo,
                pr_number=pr_number,
                cutoff=as_of,
                data_dir=data_dir,
                options=self.input_options,
            )
        return self.predictor.predict(bundle, top_k=top_k)


def _load_import_target(import_path: str):  # type: ignore[no-untyped-def]
    if ":" not in import_path:
        raise ValueError(f"invalid import_path (expected module:attr): {import_path}")
    module_name, attr_name = import_path.split(":", 1)
    mod = importlib.import_module(module_name)
    try:
        return getattr(mod, attr_name)
    except AttributeError as exc:
        raise ValueError(f"missing attribute in import path: {import_path}") from exc


def _instantiate_target(target, *, config_path: str | None):  # type: ignore[no-untyped-def]
    if inspect.isclass(target):
        if config_path is None:
            return target()
        try:
            return target(config_path=config_path)
        except TypeError:
            return target()

    if callable(target):
        if config_path is None:
            try:
                return target()
            except TypeError:
                return target(None)
        try:
            return target(config_path)
        except TypeError:
            return target(config_path=config_path)

    raise TypeError("router import target must be class or callable")


def _read_router_config_payload(*, router_name: str, config_path: str) -> dict[str, object]:
    path = Path(config_path)
    if not path.exists():
        raise ValueError(f"{router_name} config path does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {router_name} config: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{router_name} config must be a JSON object: {path}")
    return payload


def _build_mentions_router(_: str | None) -> Router:
    return MentionsRouter()


def _build_popularity_router(_: str | None) -> Router:
    return PopularityRouter(lookback_days=180)


def _build_codeowners_router(_: str | None) -> Router:
    return CodeownersRouter(enabled=True)


def _build_union_router(_: str | None) -> Router:
    return UnionRouter()


def _build_hybrid_ranker_router(config_path: str | None) -> Router:
    if config_path is None:
        return HybridRankerRouter()

    payload = _read_router_config_payload(
        router_name="hybrid_ranker",
        config_path=config_path,
    )
    try:
        validated = HybridRankerConfigPayload.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"invalid hybrid_ranker config at {config_path}: {exc}") from exc
    return HybridRankerRouter(weights=dict(validated.weights))


def _build_llm_rerank_router(config_path: str | None) -> Router:
    if config_path in {"off", "live", "replay"}:
        return LLMRerankRouter(mode=str(config_path))
    if config_path is None:
        return LLMRerankRouter(mode="replay")

    payload = _read_router_config_payload(
        router_name="llm_rerank",
        config_path=config_path,
    )
    try:
        validated = LLMRerankConfigPayload.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"invalid llm_rerank config at {config_path}: {exc}") from exc
    return LLMRerankRouter(
        mode=validated.mode,
        model_name=validated.model_name,
        cache_dir=validated.cache_dir,
    )


def _build_stewards_router(config_path: str | None) -> Router:
    if config_path is None:
        raise ValueError("config_path is required for stewards router")
    path = Path(config_path)
    if not path.exists():
        raise ValueError(f"stewards config path does not exist: {path}")
    try:
        load_scoring_config(path)
    except Exception as exc:
        raise ValueError(f"invalid stewards config at {path}: {exc}") from exc
    return StewardsRouter(config_path=path)


def _register_default_builtin_routers() -> None:
    if _BUILTIN_ROUTER_FACTORIES:
        return
    register_builtin_router("mentions", _build_mentions_router)
    register_builtin_router("popularity", _build_popularity_router)
    register_builtin_router("codeowners", _build_codeowners_router)
    register_builtin_router("union", _build_union_router)
    register_builtin_router("hybrid_ranker", _build_hybrid_ranker_router)
    register_builtin_router("llm_rerank", _build_llm_rerank_router)
    register_builtin_router("stewards", _build_stewards_router)


_register_default_builtin_routers()


def _builtin_router(name: str, *, config_path: str | None) -> Router:
    key = name.strip().lower()
    factory = _BUILTIN_ROUTER_FACTORIES.get(key)
    if factory is None:
        raise ValueError(f"unknown builtin router: {name}")
    return factory(config_path)


def _coerce_router_or_predictor(obj):  # type: ignore[no-untyped-def]
    if hasattr(obj, "route"):
        return obj
    if hasattr(obj, "predict"):
        return PredictorRouterAdapter(predictor=obj)
    raise TypeError("loaded object must implement Router.route or Predictor.predict")


def load_router(spec: RouterSpec):  # type: ignore[no-untyped-def]
    if spec.type == "builtin":
        return _builtin_router(spec.name, config_path=spec.config_path)

    if spec.type == "import_path":
        import_path = spec.import_path or spec.name
        target = _load_import_target(import_path)
        loaded = _instantiate_target(target, config_path=spec.config_path)
        return _coerce_router_or_predictor(loaded)

    raise ValueError(f"unknown router spec type: {spec.type}")


def router_manifest_entry(spec: RouterSpec) -> dict[str, object]:
    return {
        "router_id": router_id_for_spec(spec),
        "type": spec.type,
        "name": spec.name,
        "import_path": spec.import_path,
        "config_path": spec.config_path,
        "config_sha256": _config_hash(spec.config_path),
        "spec": json.loads(spec.model_dump_json()),
    }
