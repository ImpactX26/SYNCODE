"""Deterministic evidence-based confidence calculation engine."""

from __future__ import annotations

from typing import List, Optional, Tuple
from falsify.state import Evidence, Hypothesis, IncidentState


# Confidence Cap Constants
CAP_ZERO_SUPPORTING = 0.20
CAP_CONTRADICTING = 0.40
CAP_FEWER_THAN_TWO_SOURCES = 0.60
MAX_CONFIDENCE = 0.95


def get_leading_hypothesis(hypotheses: List[Hypothesis]) -> Optional[Hypothesis]:
    """Identify the primary leading hypothesis based on net supporting evidence and alive status."""
    if not hypotheses:
        return None

    # Prioritize alive hypotheses first, then uncertain
    alive = [h for h in hypotheses if h.status == "alive"]
    candidates = alive if alive else [h for h in hypotheses if h.status != "falsified"]
    if not candidates:
        # If all are falsified, return the first one
        return hypotheses[0]

    def score_hypothesis(h: Hypothesis) -> Tuple[int, int, int]:
        supporting = sum(1 for e in h.evidence if e.classification == "supports")
        contradicting = sum(1 for e in h.evidence if e.classification == "contradicts")
        net = supporting - contradicting
        # Tuple for sorting: (net_evidence, supporting_count, is_alive)
        return (net, supporting, 1 if h.status == "alive" else 0)

    return max(candidates, key=score_hypothesis)


def calculate_confidence_for_hypothesis(
    lead: Hypothesis,
    rivals: Optional[List[Hypothesis]] = None,
) -> float:
    """Calculate deterministic confidence score for a specific hypothesis.
    
    Deterministic Rules:
      1. If hypothesis is 'falsified', confidence is 0.0.
      2. Zero supporting evidence caps confidence at 0.20 (CAP_ZERO_SUPPORTING).
      3. Contradicting evidence against lead hypothesis caps confidence at 0.40 (CAP_CONTRADICTING).
      4. Supporting evidence from fewer than 2 independent sources caps confidence at 0.60 (CAP_FEWER_THAN_TWO_SOURCES).
      5. Additional independent supporting evidence increases base score.
      6. Falsified rival hypotheses increase confidence (+0.05 per falsified rival).
      7. Maximum confidence is strictly capped at 0.95 (MAX_CONFIDENCE).
    """
    if lead.status == "falsified":
        return 0.0

    supporting_ev = [e for e in lead.evidence if e.classification == "supports"]
    contradicting_ev = [e for e in lead.evidence if e.classification == "contradicts"]
    sources = set(e.source for e in supporting_ev)

    # Base score computation
    num_supporting = len(supporting_ev)
    num_sources = len(sources)

    if num_supporting == 0:
        base_score = 0.10
    elif num_sources == 1:
        # Single source signal: 0.40 base + up to 0.10 for multiple items from same source
        base_score = 0.40 + min(0.10, 0.05 * (num_supporting - 1))
    else:
        # Multi-source independent corroboration: starts at 0.65
        base_score = 0.65 + min(0.20, 0.08 * (num_sources - 2) + 0.04 * (num_supporting - num_sources))

    # Boost for falsified rivals
    rival_boost = 0.0
    if rivals:
        falsified_rivals = sum(1 for r in rivals if r.id != lead.id and r.status == "falsified")
        rival_boost = min(0.15, 0.05 * falsified_rivals)

    score = base_score + rival_boost

    # If lead status is 'uncertain', penalize base score
    if lead.status == "uncertain":
        score = min(score, 0.45)

    # --- Apply Hard Caps ---

    # Cap 1: Zero supporting evidence
    if num_supporting == 0:
        score = min(score, CAP_ZERO_SUPPORTING)

    # Cap 2: Any contradicting evidence
    if len(contradicting_ev) > 0:
        # Contradicting evidence severely limits confidence
        score = min(score, CAP_CONTRADICTING)

    # Cap 3: Supporting evidence from fewer than 2 independent sources
    if num_sources < 2:
        score = min(score, CAP_FEWER_THAN_TWO_SOURCES)

    # Cap 4: Absolute maximum confidence
    score = min(score, MAX_CONFIDENCE)
    score = max(0.0, score)

    return round(score, 4)


def calculate_confidence(hypotheses: List[Hypothesis]) -> float:
    """Calculate overall deterministic confidence score from gathered evidence.
    
    Compatible with IncidentState and LangGraph orchestration.
    """
    if not hypotheses:
        return 0.0

    lead = get_leading_hypothesis(hypotheses)
    if not lead:
        return 0.0

    rivals = [h for h in hypotheses if h.id != lead.id]
    return calculate_confidence_for_hypothesis(lead, rivals=rivals)


def update_state_confidence(state: IncidentState) -> IncidentState:
    """Convenience helper to update an IncidentState in place with newly computed confidence."""
    state.confidence = calculate_confidence(state.hypotheses)
    return state
