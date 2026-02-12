from __future__ import annotations

from repo_routing.parsing.gates import GateFields
from repo_routing.scoring.confidence import confidence_from_scores
from repo_routing.scoring.config import ThresholdsConfig
from repo_routing.scoring.decay import decay_weight
from repo_routing.scoring.risk import risk_from_inputs


def test_decay_weight_half_life() -> None:
    assert decay_weight(0.0, 10.0) == 1.0
    assert round(decay_weight(10.0, 10.0), 6) == 0.5


def test_confidence_from_scores() -> None:
    thresholds = ThresholdsConfig(confidence_high_margin=0.2, confidence_med_margin=0.1)
    assert confidence_from_scores([1.0, 0.7], thresholds) == "high"
    assert confidence_from_scores([1.0, 0.89], thresholds) == "medium"
    assert confidence_from_scores([1.0, 0.99], thresholds) == "low"


def test_risk_from_inputs() -> None:
    gates = GateFields(issue="#1", ai_disclosure="AI: no", provenance="human")
    assert risk_from_inputs(gates=gates, areas=["src"], has_candidates=True) == "medium"
    assert risk_from_inputs(gates=gates, areas=[], has_candidates=True) == "high"
