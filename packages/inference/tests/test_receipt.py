from __future__ import annotations

from datetime import datetime, timezone

from repo_routing.analysis.models import AnalysisResult, CandidateAnalysis, CandidateFeatures
from repo_routing.parsing.gates import GateFields
from repo_routing.receipt.render import render_receipt


def test_render_receipt_snapshot() -> None:
    result = AnalysisResult(
        repo="acme/widgets",
        pr_number=1,
        cutoff=datetime(2024, 1, 1, tzinfo=timezone.utc),
        gates=GateFields(issue="#1", ai_disclosure="AI: no", provenance="human"),
        areas=["src", "docs"],
        candidates=[
            CandidateAnalysis(
                login="bob",
                score=1.0,
                features=CandidateFeatures(activity_total=0.8, area_overlap_activity=0.5),
            )
        ],
        risk="medium",
        confidence="high",
    )

    expected = (
        "# PR Receipt\n"
        "\n"
        "- Repo: acme/widgets\n"
        "- PR: #1\n"
        "- Cutoff: 2024-01-01T00:00:00+00:00\n"
        "- Risk: medium\n"
        "- Confidence: high\n"
        "\n"
        "## Gates\n"
        "- Issue linked: yes\n"
        "- AI disclosure: yes\n"
        "- Provenance: yes\n"
        "\n"
        "## Areas\n"
        "- src, docs\n"
        "\n"
        "## Suggested Stewards\n"
        "- bob (score=1.000, activity_total=0.800, area_overlap=0.500)\n"
    )

    assert render_receipt(result) == expected
