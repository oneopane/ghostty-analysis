from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import re
from pathlib import Path

from pydantic import BaseModel

from .inputs.builder import build_pr_input_bundle
from .inputs.models import PRInputBuilderOptions
from .predictor.base import Predictor
from .predictor.pipeline import PipelinePredictor
from .router.base import Router
from .router.baselines.codeowners import CodeownersRouter
from .router.baselines.mentions import MentionsRouter
from .router.baselines.popularity import PopularityRouter
from .router.stewards import StewardsRouter


class RouterSpec(BaseModel):
    type: str
    name: str
    import_path: str | None = None
    config_path: str | None = None


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
    ):
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


def _builtin_router(name: str, *, config_path: str | None) -> Router:
    n = name.strip().lower()
    if n == "mentions":
        return MentionsRouter()
    if n == "popularity":
        return PopularityRouter(lookback_days=180)
    if n == "codeowners":
        return CodeownersRouter(enabled=True)
    if n == "stewards":
        if config_path is None:
            raise ValueError("config_path is required for stewards router")
        return StewardsRouter(config_path=config_path)
    raise ValueError(f"unknown builtin router: {name}")


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
