"""Tests for IncidentState, Hypothesis, and Evidence Pydantic schema validation."""

import pytest
from pydantic import ValidationError
from falsify.state import Evidence, Hypothesis, IncidentState


def test_evidence_model():
    """Verify Evidence instantiation and defaults."""
    ev = Evidence(
        source="metrics",
        claim="CPU exhaustion",
        finding="CPU usage at 99%",
        classification="supports",
    )
    assert ev.id.startswith("ev_")
    assert ev.classification == "supports"
    assert ev.data == {}


def test_hypothesis_model():
    """Verify Hypothesis schema constraints and allowed status values."""
    hyp = Hypothesis(
        claim="Connection pool exhausted",
        prediction="Active connections equal max_connections",
        status="alive",
    )
    assert hyp.id.startswith("hyp_")
    assert hyp.status == "alive"
    assert hyp.evidence == []

    # Valid statuses
    for valid_status in ["alive", "falsified", "uncertain"]:
        h = Hypothesis(claim="test", prediction="test", status=valid_status)
        assert h.status == valid_status

    # Invalid status should fail validation
    with pytest.raises(ValidationError):
        Hypothesis(claim="test", prediction="test", status="invalid_status")  # type: ignore


def test_incident_state_model():
    """Verify IncidentState schema constraints and allowed decision values."""
    state = IncidentState(title="High 500 error rate")
    assert state.incident_id.startswith("inc_")
    assert state.confidence == 0.0
    assert state.decision == "pending"
    assert state.iterations == 0
    assert state.actions_taken == []

    # Valid decisions
    for valid_decision in ["auto", "approve", "escalate", "pending"]:
        s = IncidentState(decision=valid_decision)
        assert s.decision == valid_decision

    # Invalid decision should fail validation
    with pytest.raises(ValidationError):
        IncidentState(decision="unapproved")  # type: ignore
