from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations


def cochange_scores(file_sets: list[list[str]]) -> dict[str, dict[str, float]]:
    file_freq: Counter[str] = Counter()
    pair_freq: Counter[tuple[str, str]] = Counter()

    for file_set in file_sets:
        uniq = sorted(set(file_set))
        for f in uniq:
            file_freq[f] += 1
        for a, b in combinations(uniq, 2):
            pair_freq[(a, b)] += 1

    out: dict[str, dict[str, float]] = defaultdict(dict)
    for (a, b), c in pair_freq.items():
        ca = file_freq[a]
        cb = file_freq[b]
        if ca > 0:
            out[a][b] = float(c) / float(ca)
        if cb > 0:
            out[b][a] = float(c) / float(cb)

    return {k: dict(sorted(v.items())) for k, v in sorted(out.items())}
