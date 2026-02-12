from __future__ import annotations

from collections import defaultdict

from ..parsers.models import ParserRunResult
from .path import boundary_id_for_name, boundary_name_for_path


def _module_to_boundary_id(*, module: str, file_path: str) -> str | None:
    token = module.strip()
    if not token:
        return None

    # Relative imports are anchored to the current file's top-level boundary.
    if token.startswith("."):
        return boundary_id_for_name(boundary_name_for_path(file_path))

    if token.startswith("@"):
        # Scoped package import (@scope/pkg) -> pkg
        scoped_parts = [p for p in token.split("/") if p]
        if not scoped_parts:
            return None
        token = scoped_parts[1] if len(scoped_parts) > 1 else scoped_parts[0].lstrip("@")
    else:
        token = token.lstrip("/").split("/", 1)[0]

    token = token.split(".", 1)[0].strip()
    if not token or token in {".", ".."}:
        return None
    return boundary_id_for_name(token)


def parser_boundary_votes(result: ParserRunResult) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = defaultdict(dict)

    for f in result.files:
        scores: dict[str, float] = defaultdict(float)
        for imp in f.imports:
            boundary_id = _module_to_boundary_id(module=imp.module, file_path=f.path)
            if boundary_id is None:
                continue
            scores[boundary_id] += 1.0

        total = float(sum(scores.values()))
        if total <= 0:
            continue
        out[f.path] = {
            bid: (float(v) / total)
            for bid, v in sorted(scores.items(), key=lambda kv: kv[0])
        }

    return {k: out[k] for k in sorted(out)}
