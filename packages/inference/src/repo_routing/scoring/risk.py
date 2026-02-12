from __future__ import annotations

from ..parsing.gates import GateFields


def risk_from_inputs(
    *,
    gates: GateFields,
    boundaries: list[str],
    has_candidates: bool,
) -> str:
    if gates.missing_issue or gates.missing_ai_disclosure or gates.missing_provenance:
        return "high"
    if not boundaries:
        return "high"
    if not has_candidates:
        return "high"
    return "medium"
