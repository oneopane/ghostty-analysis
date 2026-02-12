from __future__ import annotations

from collections import defaultdict

from ..parsers.models import ParserRunResult


def parser_boundary_votes(result: ParserRunResult) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = defaultdict(dict)

    for f in result.files:
        if not f.path.endswith(".py"):
            continue
        scores: dict[str, float] = defaultdict(float)
        for imp in f.imports:
            top = imp.module.split(".", 1)[0].strip()
            if not top:
                continue
            scores[f"dir:{top}"] += 1.0

        total = float(sum(scores.values()))
        if total <= 0:
            continue
        out[f.path] = {
            bid: (float(v) / total)
            for bid, v in sorted(scores.items(), key=lambda kv: kv[0])
        }

    return {k: out[k] for k in sorted(out)}
