"""Safety decision gate for remediation actions."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field
from falsify.state import DecisionStatus, IncidentState


class GateConfig(BaseModel):
    """Thresholds for automated execution vs approval requirements."""

    auto_threshold: float = Field(default=0.85, description="Minimum confidence score required for auto-remediation")
    approve_threshold: float = Field(default=0.60, description="Minimum confidence score required for human-approved action")
    high_blast_radius_auto_allowed: bool = Field(default=False, description="Whether auto-remediation is allowed for high blast radius")


def evaluate_decision_gate(state: IncidentState, config: GateConfig | None = None) -> DecisionStatus:
    """Evaluate decision gate according to confidence score and blast radius (A4 Stub).
    
    Rules:
      - If confidence >= auto_threshold and (blast_radius is low/medium or high_blast_radius_auto_allowed) -> 'auto'
      - Else if confidence >= approve_threshold -> 'approve'
      - Else -> 'escalate'
    """
    # Scaffolding stub - full gate logic implemented in Phase A4
    return "pending"
