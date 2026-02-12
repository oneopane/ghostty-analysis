from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .registry import RouterSpec, builtin_router_names, router_id_for_spec


def normalize_builtin_router_names(
    values: Iterable[str],
    *,
    option_name: str,
    require_non_empty: bool = False,
) -> list[str]:
    normalized = [str(v).strip().lower() for v in values if str(v).strip()]
    if require_non_empty and not normalized:
        raise ValueError(f"at least one {option_name} is required")

    valid = set(builtin_router_names())
    unknown = sorted({b for b in normalized if b not in valid})
    if unknown:
        valid_csv = ", ".join(sorted(valid))
        raise ValueError(
            f"unknown {option_name}(s): {', '.join(unknown)}. valid: {valid_csv}"
        )
    return normalized


def apply_router_configs(
    *,
    specs: list[RouterSpec],
    router_configs: list[str],
) -> list[RouterSpec]:
    if not router_configs:
        return specs

    keyed = [c for c in router_configs if "=" in c]
    positional = [c for c in router_configs if "=" not in c]
    out = [s.model_copy() for s in specs]

    if keyed:
        mapping: dict[str, str] = {}
        for item in keyed:
            key, value = item.split("=", 1)
            if not key.strip() or not value.strip():
                raise ValueError(f"invalid --router-config pair: {item}")
            mapping[key.strip()] = value.strip()

        for i, spec in enumerate(out):
            rid = router_id_for_spec(spec)
            if rid in mapping:
                out[i] = spec.model_copy(update={"config_path": mapping[rid]})
            elif spec.name in mapping:
                out[i] = spec.model_copy(update={"config_path": mapping[spec.name]})

    if positional:
        if len(positional) > len(out):
            raise ValueError("too many --router-config values for routers")
        for i, cfg in enumerate(positional):
            out[i] = out[i].model_copy(update={"config_path": cfg})

    return out


def build_router_specs(
    *,
    routers: list[str],
    baselines: list[str] | None = None,
    router_imports: list[str] | None = None,
    router_configs: list[str] | None = None,
    default_builtin: str = "mentions",
    stewards_config_required_message: str = "--router-config is required when router includes stewards",
) -> list[RouterSpec]:
    baseline_values = normalize_builtin_router_names(
        baselines or [],
        option_name="baseline",
    )
    router_values = normalize_builtin_router_names(
        routers,
        option_name="router",
    )

    specs: list[RouterSpec] = [
        RouterSpec(type="builtin", name=name)
        for name in [*baseline_values, *router_values]
    ]
    specs.extend(
        [
            RouterSpec(type="import_path", name=import_path, import_path=import_path)
            for import_path in (router_imports or [])
        ]
    )
    if not specs:
        specs = [RouterSpec(type="builtin", name=default_builtin)]

    specs = apply_router_configs(specs=specs, router_configs=list(router_configs or []))

    for spec in specs:
        if spec.type == "builtin" and spec.name == "stewards":
            if spec.config_path is None:
                raise ValueError(stewards_config_required_message)
            p = Path(spec.config_path)
            if not p.exists():
                raise ValueError(f"router config path does not exist: {p}")

    return specs
