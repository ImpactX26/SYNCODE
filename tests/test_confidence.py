"""Comprehensive unit tests for deterministic evidence-based confidence engine."""

import pytest
from falsify.confidence import (
    CAP_CONTRADICTING,
    CAP_FEWER_THAN_TWO_SOURCES,
    CAP_ZERO_SUPPORTING,
    MAX_CONFIDENCE,
    calculate_confidence,
    calculate_confidence_for_hypothesis,
    get_leading_hypothesis,
    update_state_confidence,
)
from falsify.state import Evidence, Hypothesis, IncidentState


def test_confidence_constants():
    """Verify confidence threshold constants."""
    assert CAP_ZERO_SUPPORTING == 0.20
    assert CAP_CONTRADICTING == 0.40
    assert CAP_FEWER_THAN_TWO_SOURCES == 0.60
    assert MAX_CONFIDENCE == 0.95


def test_empty_hypotheses():
    """Verify empty hypothesis list returns 0.0 confidence."""
    assert calculate_confidence([]) == 0.0


def test_zero_supporting_evidence_cap():
    """Verify hypothesis with zero supporting evidence is capped at 0.20."""
    hyp = Hypothesis(
        claim="Memory leak in auth service",
        prediction="RSS memory steadily grows over time",
        evidence=[],
    )
    conf = calculate_confidence([hyp])
    assert conf <= CAP_ZERO_SUPPORTING
    assert conf > 0.0


def test_single_source_cap():
    """Verify hypothesis with supporting evidence from only 1 source is capped at 0.60."""
    ev1 = Evidence(
        source="metrics",
        claim="CPU exhaustion",
        finding="CPU usage is 98%",
        classification="supports",
    )
    ev2 = Evidence(
        source="metrics",
        claim="CPU exhaustion",
        finding="CPU load average is 16.0",
        classification="supports",
    )
    ev3 = Evidence(
        source="metrics",
        claim="CPU exhaustion",
        finding="Throttling rate is 45%",
        classification="supports",
    )
    hyp = Hypothesis(
        claim="CPU exhaustion in gateway",
        prediction="CPU metrics exceed 90%",
        evidence=[ev1, ev2, ev3],
    )
    conf = calculate_confidence([hyp])
    assert conf <= CAP_FEWER_THAN_TWO_SOURCES
    assert conf >= 0.40


def test_contradicting_evidence_cap():
    """Verify hypothesis with contradicting evidence is capped at 0.40."""
    ev_sup1 = Evidence(
        source="metrics",
        claim="OOM Kill",
        finding="Memory at 99%",
        classification="supports",
    )
    ev_sup2 = Evidence(
        source="logs",
        claim="OOM Kill",
        finding="Killed process 1234 (python)",
        classification="supports",
    )
    ev_contra = Evidence(
        source="probe",
        claim="OOM Kill",
        finding="Service response HTTP 200 returned normally",
        classification="contradicts",
    )
    hyp = Hypothesis(
        claim="Service died due to OOM",
        prediction="Container terminated with exit code 137",
        evidence=[ev_sup1, ev_sup2, ev_contra],
    )
    conf = calculate_confidence([hyp])
    assert conf <= CAP_CONTRADICTING


def test_multi_source_corroboration():
    """Verify independent multi-source evidence achieves higher confidence (> 0.60)."""
    ev_metrics = Evidence(
        source="metrics",
        claim="DB pool exhausted",
        finding="Active connections == max_connections (100/100)",
        classification="supports",
    )
    ev_logs = Evidence(
        source="logs",
        claim="DB pool exhausted",
        finding="TimeoutAcquiringConnectionException: Pool exhausted",
        classification="supports",
    )
    ev_db = Evidence(
        source="get_db_stats",
        claim="DB pool exhausted",
        finding="waiting_threads: 48",
        classification="supports",
    )
    hyp = Hypothesis(
        claim="Database connection pool exhaustion",
        prediction="DB pool capacity reached and logs show acquisition timeout",
        evidence=[ev_metrics, ev_logs, ev_db],
    )
    conf = calculate_confidence([hyp])
    assert conf > CAP_FEWER_THAN_TWO_SOURCES
    assert conf <= MAX_CONFIDENCE


def test_falsified_rivals_boost():
    """Verify confidence in leading hypothesis increases when rival hypotheses are falsified."""
    ev1 = Evidence(
        source="metrics",
        claim="DB pool exhausted",
        finding="Active connections 100/100",
        classification="supports",
    )
    ev2 = Evidence(
        source="logs",
        claim="DB pool exhausted",
        finding="Pool exhausted error",
        classification="supports",
    )
    lead = Hypothesis(
        id="hyp_lead",
        claim="DB pool exhausted",
        prediction="Active connections == max",
        status="alive",
        evidence=[ev1, ev2],
    )

    rival_alive = Hypothesis(
        id="hyp_rival1",
        claim="Network partition",
        prediction="Gateway packet drop",
        status="alive",
    )

    rival_falsified = Hypothesis(
        id="hyp_rival2",
        claim="High memory leak",
        prediction="RSS high",
        status="falsified",
    )

    conf_with_alive_rival = calculate_confidence([lead, rival_alive])
    conf_with_falsified_rival = calculate_confidence([lead, rival_falsified])

    assert conf_with_falsified_rival > conf_with_alive_rival


def test_max_confidence_cap():
    """Verify confidence is strictly capped at MAX_CONFIDENCE (0.95)."""
    ev_list = [
        Evidence(source=f"source_{i}", claim="Root cause", finding=f"finding_{i}", classification="supports")
        for i in range(10)
    ]
    lead = Hypothesis(
        id="lead",
        claim="Definitive root cause",
        prediction="All signals point here",
        status="alive",
        evidence=ev_list,
    )
    rivals = [
        Hypothesis(id=f"r_{i}", claim=f"Rival {i}", prediction="p", status="falsified")
        for i in range(5)
    ]

    conf = calculate_confidence([lead] + rivals)
    assert conf <= MAX_CONFIDENCE
    assert conf == 0.95


def test_falsified_lead_hypothesis():
    """Verify falsified hypothesis gets 0.0 confidence."""
    hyp = Hypothesis(
        claim="Faulty deploy",
        prediction="Bad commit hash",
        status="falsified",
        evidence=[Evidence(source="deploy", claim="x", finding="y", classification="supports")],
    )
    assert calculate_confidence([hyp]) == 0.0


def test_get_leading_hypothesis():
    """Verify get_leading_hypothesis picks alive hypothesis with highest net supporting evidence."""
    h1 = Hypothesis(id="h1", claim="Cause 1", prediction="p1", status="alive", evidence=[])
    ev = Evidence(source="metrics", claim="Cause 2", finding="ok", classification="supports")
    h2 = Hypothesis(id="h2", claim="Cause 2", prediction="p2", status="alive", evidence=[ev])
    h3 = Hypothesis(id="h3", claim="Cause 3", prediction="p3", status="falsified", evidence=[ev, ev])

    lead = get_leading_hypothesis([h1, h2, h3])
    assert lead is not None
    assert lead.id == "h2"


def test_update_state_confidence():
    """Verify update_state_confidence updates IncidentState.confidence deterministically."""
    ev = Evidence(source="logs", claim="Error", finding="500", classification="supports")
    hyp = Hypothesis(claim="Bug", prediction="error log", evidence=[ev])
    state = IncidentState(hypotheses=[hyp])
    assert state.confidence == 0.0

    update_state_confidence(state)
    assert state.confidence > 0.0
    assert state.confidence <= CAP_FEWER_THAN_TWO_SOURCES
