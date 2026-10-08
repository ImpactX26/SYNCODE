"""Placeholder tests for multi-signal crosschecking and evidence evaluation."""

from falsify.state import Evidence, Hypothesis


def test_crosscheck_evidence_linking():
    """Verify evidence can be associated with competing hypotheses."""
    hyp_a = Hypothesis(claim="Service A crash", prediction="Service A restart count > 0")
    hyp_b = Hypothesis(claim="Network partition", prediction="Connection drops on gateway")

    ev_a = Evidence(
        source="metrics",
        claim=hyp_a.claim,
        finding="Restarts: 0",
        classification="contradicts",
    )
    ev_b = Evidence(
        source="probe",
        claim=hyp_b.claim,
        finding="Gateway timeout 504",
        classification="supports",
    )

    hyp_a.evidence.append(ev_a)
    hyp_b.evidence.append(ev_b)

    assert len(hyp_a.evidence) == 1
    assert hyp_a.evidence[0].classification == "contradicts"
    assert len(hyp_b.evidence) == 1
    assert hyp_b.evidence[0].classification == "supports"
