"""Falsify shared incident state models."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


EvidenceClassification = Literal["supports", "contradicts", "inconclusive"]
HypothesisStatus = Literal["alive", "falsified", "uncertain"]
DecisionStatus = Literal["auto", "approve", "escalate", "pending"]


class Evidence(BaseModel):
    """Evidence gathered during incident investigation."""

    id: str = Field(default_factory=lambda: f"ev_{int(time.time() * 1000)}")
    source: str = Field(..., description="Source of the evidence (e.g. metrics, logs, probe, deploy_history)")
    claim: str = Field(..., description="The specific proposition being tested or observed")
    finding: str = Field(..., description="Observed outcome or factual data snippet")
    classification: EvidenceClassification = Field(..., description="Evidence relation to hypothesis: supports, contradicts, or inconclusive")
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp of when evidence was gathered")
    data: Dict[str, Any] = Field(default_factory=dict, description="Raw or parsed telemetry data payload")


class Hypothesis(BaseModel):
    """Competing hypothesis explaining the root cause of an incident."""

    id: str = Field(default_factory=lambda: f"hyp_{int(time.time() * 1000)}")
    claim: str = Field(..., description="Proposed root cause explanation")
    prediction: str = Field(..., description="Verifiable prediction if this claim is true")
    status: HypothesisStatus = Field(default="alive", description="Status of hypothesis: alive, falsified, or uncertain")
    evidence: List[Evidence] = Field(default_factory=list, description="Evidence gathered for or against this hypothesis")
    created_at: float = Field(default_factory=time.time, description="Creation timestamp")


class IncidentState(BaseModel):
    """Shared state of an active or resolved incident."""

    incident_id: str = Field(default_factory=lambda: f"inc_{int(time.time())}", description="Unique incident identifier")
    title: str = Field(default="", description="Incident summary or alert title")
    status: str = Field(default="investigating", description="High-level workflow status")
    blast_radius: str = Field(default="unknown", description="Assessed impact blast radius: low, medium, high, critical")
    hypotheses: List[Hypothesis] = Field(default_factory=list, description="List of competing hypotheses")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Calculated confidence score [0.0, 1.0]")
    decision: DecisionStatus = Field(default="pending", description="Decision outcome: auto, approve, escalate, pending")
    iterations: int = Field(default=0, ge=0, description="Number of investigation/verification loop iterations executed")
    actions_taken: List[Dict[str, Any]] = Field(default_factory=list, description="Record of executed remediation actions")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata, targets, and trigger payloads")
    events: List[Dict[str, Any]] = Field(default_factory=list, description="Audit log of timeline events emitted during the lifecycle")
    errors: List[str] = Field(default_factory=list, description="Recorded non-fatal errors or warnings during orchestration")
