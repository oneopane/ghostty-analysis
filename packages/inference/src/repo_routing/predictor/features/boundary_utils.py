from __future__ import annotations

from collections import Counter
from typing import Iterable


def primary_boundary_name(boundary_id: str) -> str:
    return boundary_id.removeprefix("dir:")


def boundary_counts_from_file_boundaries(
    file_boundaries: dict[str, list[str]],
) -> Counter[str]:
    counter: Counter[str] = Counter()
    for _path, boundary_ids in sorted(file_boundaries.items()):
        if not boundary_ids:
            continue
        counter[str(boundary_ids[0])] += 1
    return counter


def boundary_weight_dot(
    left: dict[str, float],
    right: dict[str, float],
) -> float:
    if len(left) > len(right):
        left, right = right, left
    return float(sum(float(v) * float(right.get(k, 0.0)) for k, v in left.items()))


def overlap_ratio(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = {str(x) for x in left}
    right_set = {str(x) for x in right}
    if not left_set:
        return 0.0
    return float(len(left_set & right_set)) / float(len(left_set))
