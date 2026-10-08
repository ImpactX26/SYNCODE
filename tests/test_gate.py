"""Placeholder tests for safety decision gate."""

from falsify.gate import GateConfig, evaluate_decision_gate
from falsify.state import IncidentState


def test_gate_config_defaults():
    """Verify default decision gate thresholds."""
    config = GateConfig()
    assert config.auto_threshold == 0.85
    assert config.approve_threshold == 0.60
    assert config.high_blast_radius_auto_allowed is False


def test_evaluate_decision_gate_stub():
    """Verify decision gate stub interface."""
    state = IncidentState(title="High error rate")
    decision = evaluate_decision_gate(state)
    assert decision in ("auto", "approve", "escalate", "pending")
