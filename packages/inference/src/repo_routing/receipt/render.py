from __future__ import annotations

from ..analysis.models import AnalysisResult


def _format_bool(value: bool) -> str:
    return "yes" if value else "no"


def render_receipt(result: AnalysisResult, *, max_candidates: int = 5) -> str:
    lines: list[str] = []
    lines.append("# PR Receipt")
    lines.append("")
    lines.append(f"- Repo: {result.repo}")
    lines.append(f"- PR: #{result.pr_number}")
    lines.append(f"- Cutoff: {result.cutoff.isoformat()}")
    lines.append(f"- Risk: {result.risk}")
    lines.append(f"- Confidence: {result.confidence}")
    lines.append("")

    lines.append("## Gates")
    lines.append(f"- Issue linked: {_format_bool(not result.gates.missing_issue)}")
    lines.append(
        f"- AI disclosure: {_format_bool(not result.gates.missing_ai_disclosure)}"
    )
    lines.append(
        f"- Provenance: {_format_bool(not result.gates.missing_provenance)}"
    )
    lines.append("")

    lines.append("## Boundaries")
    if result.boundaries:
        lines.append("- " + ", ".join(result.boundaries))
    else:
        lines.append("- No boundaries detected")
    lines.append("")

    lines.append("## Suggested Stewards")
    if result.candidates:
        for c in result.candidates[:max_candidates]:
            lines.append(
                f"- {c.login} (score={c.score:.3f}, "
                f"activity_total={c.features.activity_total:.3f}, "
                f"boundary_overlap={c.features.boundary_overlap_activity:.3f})"
            )
    else:
        lines.append("- No candidates found")

    if result.notes:
        lines.append("")
        lines.append("## Notes")
        for note in result.notes:
            lines.append(f"- {note}")

    return "\n".join(lines).rstrip() + "\n"
