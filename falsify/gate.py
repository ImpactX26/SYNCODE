"""Safety decision gate for remediation actions and policy enforcement."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, Field

from falsify.state import DecisionStatus, Hypothesis, IncidentState

# Explicit allow-list of approved remediation actions
ALLOWED_ACTIONS = {
    "restart_service",
    "rollback_deploy",
    "scale_service",
}


class GateConfig(BaseModel):
    """Thresholds for automated execution vs approval requirements."""

    auto_threshold: float = Field(
        default=0.80,
        description="Minimum deterministic confidence score required for auto-remediation",
    )
    approve_threshold: float = Field(
        default=0.60,
        description="Minimum deterministic confidence score required for human-approved action",
    )
    high_blast_radius_auto_allowed: bool = Field(
        default=False,
        description="Whether auto-remediation is permitted for high or critical blast radius",
    )
    min_supporting_evidence: int = Field(
        default=1,
        description="Minimum number of supporting evidence items required before taking action",
    )


class GateEvaluationResult(BaseModel):
    """Detailed result of safety gate policy check."""

    decision: DecisionStatus
    allowed: bool
    reason: str
    action_name: Optional[str] = None


def is_action_allowed(action_name: str) -> bool:
    """Verify whether action name is within the explicit allow-list."""
    if not action_name:
        return False
    return action_name.strip() in ALLOWED_ACTIONS


def is_false_alarm(state: IncidentState) -> Tuple[bool, str]:
    """Check if the incident is a false alarm requiring no action."""
    # 1. Explicit metadata marker from triage
    if state.metadata.get("is_real_incident") is False:
        return True, "Triage classified alert as not a real incident (false alarm)."

    # 2. No hypotheses alive or all falsified
    if state.hypotheses:
        all_falsified = all(h.status == "falsified" for h in state.hypotheses)
        if all_falsified:
            return True, "All proposed failure hypotheses have been falsified."

    return False, ""


def is_ambiguous(state: IncidentState) -> Tuple[bool, str]:
    """Check if the incident diagnosis is ambiguous between competing causes."""
    alive_hypotheses = [h for h in state.hypotheses if h.status == "alive"]

    # If multiple alive hypotheses exist, check for ambiguity
    if len(alive_hypotheses) >= 2:
        # Check supporting evidence counts on top hypotheses
        sorted_by_evidence = sorted(
            alive_hypotheses,
            key=lambda h: sum(1 for e in h.evidence if e.classification == "supports"),
            reverse=True,
        )
        h1 = sorted_by_evidence[0]
        h2 = sorted_by_evidence[1]
        s1 = sum(1 for e in h1.evidence if e.classification == "supports")
        s2 = sum(1 for e in h2.evidence if e.classification == "supports")

        # If both top hypotheses have equal supporting evidence > 0, state is ambiguous
        if s1 > 0 and s1 == s2:
            return True, f"Ambiguous diagnosis: '{h1.claim}' and '{h2.claim}' have equal supporting evidence ({s1})."

    # If leading hypothesis has uncertain status
    if state.hypotheses:
        leading = max(state.hypotheses, key=lambda h: sum(1 for e in h.evidence if e.classification == "supports"))
        if leading.status == "uncertain":
            return True, f"Leading hypothesis '{leading.claim}' status is uncertain."

    return False, ""


def evaluate_decision_gate(
    state: IncidentState,
    config: Optional[GateConfig] = None,
) -> DecisionStatus:
    """Evaluate decision gate according to confidence score, evidence count, blast radius, and ambiguity.
    
    Rules:
      1. False alarm -> 'escalate' (No action permitted).
      2. Ambiguous diagnosis -> 'escalate' (Competing causes unresolved).
      3. Insufficient confidence (< approve_threshold) -> 'escalate'.
      4. High/critical blast radius -> 'approve' (requires human confirmation unless explicit override).
      5. Confidence >= auto_threshold and low/medium blast radius -> 'auto'.
      6. Confidence >= approve_threshold -> 'approve'.
    """
    cfg = config or GateConfig()

    # Rule 1: False alarm check
    false_alarm, reason = is_false_alarm(state)
    if false_alarm:
        return "escalate"

    # Rule 2: Ambiguity check
    ambiguous, amb_reason = is_ambiguous(state)
    if ambiguous:
        return "escalate"

    # Rule 3: Insufficient confidence
    if state.confidence < cfg.approve_threshold:
        return "escalate"

    # Rule 4: Blast radius policy
    is_high_blast = state.blast_radius.lower() in ("high", "critical")
    if is_high_blast and not cfg.high_blast_radius_auto_allowed:
        # High blast radius requires human approval
        return "approve"

    # Rule 5: Auto-remediation threshold
    if state.confidence >= cfg.auto_threshold:
        return "auto"

    # Rule 6: Human approval threshold
    if state.confidence >= cfg.approve_threshold:
        return "approve"

    return "escalate"


def validate_action_execution(
    action_name: str,
    parameters: Dict[str, Any],
    state: IncidentState,
    config: Optional[GateConfig] = None,
) -> Tuple[bool, str]:
    """Validate whether an action can be executed based on allow-list and safety gate.
    
    Returns:
        (is_valid, rejection_reason_or_ok)
    """
    cfg = config or GateConfig()

    # 1. Allow-list check
    if not is_action_allowed(action_name):
        return False, f"Action '{action_name}' is not in the explicit remediation allow-list {list(ALLOWED_ACTIONS)}."

    # 2. False alarm check
    false_alarm, reason = is_false_alarm(state)
    if false_alarm:
        return False, f"Action blocked: {reason}"

    # 3. Ambiguity check
    ambiguous, amb_reason = is_ambiguous(state)
    if ambiguous:
        return False, f"Action blocked: {amb_reason}"

    # 4. Confidence check
    if state.confidence < cfg.approve_threshold:
        return (
            False,
            f"Action blocked: Confidence {state.confidence:.2f} is below approval threshold {cfg.approve_threshold:.2f}.",
        )

    # 5. Target container verification (only demo containers)
    service_target = parameters.get("service_name") or parameters.get("target") or ""
    if service_target and not (service_target.startswith("falsify-demo-") or "demo" in service_target or "mock" in service_target):
        # Target must be demo/mock container
        return False, f"Action blocked: Remediation target '{service_target}' must be a demo container."

    return True, "Action approved by safety gate."
