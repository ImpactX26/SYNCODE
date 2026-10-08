"""Comprehensive tests for Safety Decision Gate and policy enforcement."""

import pytest
from falsify.gate import (
    ALLOWED_ACTIONS,
    GateConfig,
    evaluate_decision_gate,
    is_action_allowed,
    is_ambiguous,
    is_false_alarm,
    validate_action_execution,
)
from falsify.state import Evidence, Hypothesis, IncidentState


def test_allowed_actions_allowlist():
    """Verify allow-list allows only designated remediation actions."""
    assert is_action_allowed("restart_service") is True
    assert is_action_allowed("rollback_deploy") is True
    assert is_action_allowed("scale_service") is True

    # Unknown or unsafe actions rejected
    assert is_action_allowed("delete_database") is False
    assert is_action_allowed("reboot_host") is False
    assert is_action_allowed("rm_rf") is False
    assert is_action_allowed("") is False


def test_insufficient_confidence_escalates():
    """Verify insufficient confidence (< approve_threshold) escalates."""
    state = IncidentState(title="Latency Alert", confidence=0.45, blast_radius="medium")
    hyp = Hypothesis(claim="Network delay", prediction="RTT high", status="alive")
    state.hypotheses = [hyp]

    config = GateConfig(auto_threshold=0.80, approve_threshold=0.60)
    decision = evaluate_decision_gate(state, config=config)
    assert decision == "escalate"


def test_high_confidence_low_blast_radius_auto_approved():
    """Verify high confidence with low/medium blast radius is auto-approved."""
    state = IncidentState(title="Pool saturation", confidence=0.85, blast_radius="low")
    ev1 = Evidence(source="metrics", claim="Pool", finding="100/100", classification="supports")
    ev2 = Evidence(source="logs", claim="Pool", finding="Timeout", classification="supports")
    hyp = Hypothesis(claim="Pool exhaustion", prediction="full", status="alive", evidence=[ev1, ev2])
    state.hypotheses = [hyp]

    config = GateConfig(auto_threshold=0.80, approve_threshold=0.60)
    decision = evaluate_decision_gate(state, config=config)
    assert decision == "auto"


def test_high_blast_radius_requires_human_approval():
    """Verify high blast radius requires human approval even with high confidence."""
    state = IncidentState(title="Critical Outage", confidence=0.90, blast_radius="high")
    ev = Evidence(source="metrics", claim="Bug", finding="err", classification="supports")
    hyp = Hypothesis(claim="Bug", prediction="err", status="alive", evidence=[ev])
    state.hypotheses = [hyp]

    config = GateConfig(auto_threshold=0.80, approve_threshold=0.60, high_blast_radius_auto_allowed=False)
    decision = evaluate_decision_gate(state, config=config)
    assert decision == "approve"


def test_false_alarm_results_in_no_action_and_escalate():
    """Verify false alarm alerts result in no action and escalate."""
    # Case 1: Triage identified false alarm
    state_false = IncidentState(
        title="Spike in 404s",
        confidence=0.80,
        metadata={"is_real_incident": False},
    )
    assert evaluate_decision_gate(state_false) == "escalate"
    is_valid, reason = validate_action_execution("restart_service", {"service_name": "falsify-demo-web"}, state_false)
    assert is_valid is False
    assert "false alarm" in reason.lower()

    # Case 2: All hypotheses falsified
    h1 = Hypothesis(claim="Cause 1", prediction="p1", status="falsified")
    h2 = Hypothesis(claim="Cause 2", prediction="p2", status="falsified")
    state_all_falsified = IncidentState(hypotheses=[h1, h2], confidence=0.0)
    assert evaluate_decision_gate(state_all_falsified) == "escalate"


def test_ambiguous_diagnosis_escalates():
    """Verify ambiguous competing hypotheses with equal evidence escalate rather than act."""
    ev1 = Evidence(source="metrics", claim="Cause A", finding="spike A", classification="supports")
    ev2 = Evidence(source="logs", claim="Cause B", finding="error B", classification="supports")
    h_a = Hypothesis(id="ha", claim="Cause A", prediction="pA", status="alive", evidence=[ev1])
    h_b = Hypothesis(id="hb", claim="Cause B", prediction="pB", status="alive", evidence=[ev2])

    state_amb = IncidentState(
        title="Ambiguous outage",
        confidence=0.75,
        hypotheses=[h_a, h_b],
    )
    is_amb, reason = is_ambiguous(state_amb)
    assert is_amb is True
    assert "Ambiguous diagnosis" in reason

    decision = evaluate_decision_gate(state_amb)
    assert decision == "escalate"


def test_validate_action_execution_policies():
    """Verify validate_action_execution checks allowlist, confidence, and demo container target."""
    ev = Evidence(source="metrics", claim="Leak", finding="RSS", classification="supports")
    hyp = Hypothesis(claim="Leak", prediction="RSS", status="alive", evidence=[ev])
    state = IncidentState(title="Memory Leak", confidence=0.85, blast_radius="medium", hypotheses=[hyp])

    # Valid demo target action
    valid_ok, msg = validate_action_execution(
        "restart_service",
        {"service_name": "falsify-demo-payment"},
        state,
    )
    assert valid_ok is True

    # Invalid non-allowlisted action
    invalid_action, msg = validate_action_execution(
        "drop_table",
        {"service_name": "falsify-demo-payment"},
        state,
    )
    assert invalid_action is False
    assert "not in the explicit remediation allow-list" in msg

    # Invalid non-demo host container target
    invalid_target, msg = validate_action_execution(
        "restart_service",
        {"service_name": "production-k8s-master-node"},
        state,
    )
    assert invalid_target is False
    assert "must be a demo container" in msg
