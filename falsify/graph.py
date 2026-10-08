"""LangGraph orchestration and agent workflow graph for Falsify."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type, TypeVar
from pydantic import BaseModel, Field
from langgraph.graph import END, START, StateGraph

from falsify.budget import BudgetConfig, BudgetTracker
from falsify.confidence import calculate_confidence, get_leading_hypothesis, update_state_confidence
from falsify.gate import (
    ALLOWED_ACTIONS,
    GateConfig,
    evaluate_decision_gate,
    is_action_allowed,
    validate_action_execution,
)
from falsify.llm import LLMClient, LLMConfig, LLMError, LLMMalformedResponseError, LLMResponse
from falsify.sanitize import sanitize_tool_output, wrap_untrusted_context
from falsify.state import DecisionStatus, Evidence, Hypothesis, IncidentState
from falsify.tools.base import (
    ToolResult,
    get_db_stats,
    get_deploy_history,
    get_logs,
    get_metrics,
    probe_dependency,
    restart_service,
    rollback_deploy,
    scale_service,
)

T = TypeVar("T", bound=BaseModel)

# Allowed diagnostic tools registry
DIAGNOSTIC_TOOLS: Dict[str, Callable[..., ToolResult]] = {
    "get_metrics": get_metrics,
    "get_logs": get_logs,
    "get_deploy_history": get_deploy_history,
    "probe_dependency": probe_dependency,
    "get_db_stats": get_db_stats,
}

# Allowed remediation tools registry
REMEDIATION_TOOLS: Dict[str, Callable[..., ToolResult]] = {
    "restart_service": restart_service,
    "rollback_deploy": rollback_deploy,
    "scale_service": scale_service,
}


# =====================================================================
# Structured Output Schemas for Agent Nodes
# =====================================================================

class TriageOutput(BaseModel):
    """Structured response from Triage node."""
    summary: str = Field(..., description="Summary of the incident based on alert and available data")
    problem_area: str = Field(..., description="Primary suspected service, subsystem, or domain")
    blast_radius: str = Field(default="medium", description="Estimated blast radius: low, medium, high, critical")
    is_real_incident: bool = Field(default=True, description="Whether the alert constitutes a real actionable incident")


class HypothesisItem(BaseModel):
    """A single proposed competing root cause with testable prediction."""
    claim: str = Field(..., description="Specific proposed root cause mechanism")
    prediction: str = Field(..., description="Concrete, verifiable prediction observable via diagnostic tools")


class HypothesisOutput(BaseModel):
    """Structured response from Hypothesis node."""
    hypotheses: List[HypothesisItem] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="List of 2-5 competing hypotheses explaining the failure",
    )


class ExperimentSelection(BaseModel):
    """Structured response for choosing a diagnostic experiment."""
    hypothesis_claim: str = Field(..., description="Claim being tested")
    tool_name: str = Field(..., description="Allow-listed diagnostic tool name")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Parameters to pass to the tool")
    expected_observation: str = Field(..., description="What observation would support the claim")


class EvidenceEvaluation(BaseModel):
    """Structured evaluation of tool telemetry against hypothesis prediction."""
    classification: Literal["supports", "contradicts", "inconclusive"] = Field(
        ...,
        description="Whether observation supports, contradicts, or is inconclusive for the hypothesis",
    )
    finding: str = Field(..., description="Concise factual summary of the finding from tool output")


class SkepticOutput(BaseModel):
    """Structured critique from Skeptic node."""
    critique: str = Field(..., description="Critical challenge to leading hypothesis and evidence gaps")
    challenges_leading_hypothesis: bool = Field(
        default=False,
        description="Whether the leading hypothesis has flawed evidence or alternative interpretations",
    )
    suggested_status: Optional[Literal["alive", "falsified", "uncertain"]] = Field(
        default=None,
        description="Suggested new status for the leading hypothesis",
    )
    rival_to_promote_claim: Optional[str] = Field(
        default=None,
        description="Alternative rival hypothesis claim to consider",
    )


class ActionSelection(BaseModel):
    """Structured response for choosing a remediation action."""
    action_name: str = Field(..., description="Name of allow-listed remediation action to execute")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Parameters to pass to the action tool")
    rationale: str = Field(..., description="Technical rationale for why this action remediates the root cause")


class VerificationOutput(BaseModel):
    """Structured response for verifying recovery post-remediation."""
    recovered: bool = Field(..., description="Whether post-action telemetry confirms system recovery")
    finding: str = Field(..., description="Detailed factual finding from verification check")


# =====================================================================
# Helper Utilities
# =====================================================================

def emit_event(state: IncidentState, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Emit a typed timeline event matching docs/CONTRACTS.md schema."""
    event = {
        "ts": time.time(),
        "incident_id": state.incident_id,
        "type": event_type,
        "payload": payload,
    }
    state.events.append(event)
    return event


def ensure_incident_state(state: Any) -> IncidentState:
    """Ensure input is an IncidentState instance."""
    if isinstance(state, IncidentState):
        return state
    elif isinstance(state, dict):
        return IncidentState.model_validate(state)
    raise ValueError(f"Expected IncidentState or dict, got {type(state)}")


def call_llm_with_one_retry(
    client: LLMClient,
    prompt: str,
    schema: Type[T],
    system: Optional[str] = None,
) -> Tuple[Optional[T], Optional[str]]:
    """Execute LLM call and parse into Pydantic schema with exactly ONE retry on failure.
    
    Returns:
        (parsed_instance, error_message)
    """
    # Attempt 1
    try:
        parsed, _ = client.complete_pydantic(prompt=prompt, pydantic_model=schema, system=system)
        return parsed, None
    except Exception as first_error:
        # Retry ONCE with error feedback
        retry_prompt = (
            f"{prompt}\n\n"
            f"[ATTENTION: Previous attempt failed schema validation: {first_error}]\n"
            f"Please fix formatting and output strictly valid JSON conforming to the schema."
        )
        try:
            parsed, _ = client.complete_pydantic(prompt=retry_prompt, pydantic_model=schema, system=system)
            return parsed, None
        except Exception as second_error:
            return None, f"Schema validation failed after 1 retry: {second_error}"


# =====================================================================
# Agent Workflow Nodes (Phases A3 & A4)
# =====================================================================

def triage_node(
    state: IncidentState,
    client: Optional[LLMClient] = None,
    tracker: Optional[BudgetTracker] = None,
) -> IncidentState:
    """TRIAGE Node: Summarize incident, assess problem area and blast radius."""
    state = ensure_incident_state(state)
    llm = client or LLMClient()

    if tracker:
        tracker.record_llm_call()
        exceeded, reason = tracker.check_and_enforce_budget(state)
        if exceeded:
            return state

    system_prompt = (
        "You are the Triage Agent in Falsify SRE. Analyze the incoming alert and context. "
        "Assess whether this is a real incident, determine the primary problem area, and estimate blast radius."
    )
    prompt = (
        f"Incident Title: {state.title}\n"
        f"Status: {state.status}\n"
        f"Metadata: {state.metadata}\n\n"
        f"Perform triage assessment."
    )

    output, err = call_llm_with_one_retry(llm, prompt, TriageOutput, system=system_prompt)
    if output is None:
        state.errors.append(f"Triage failed: {err}")
        state.decision = "escalate"
        return state

    if not state.title and output.summary:
        state.title = output.summary[:80]

    state.blast_radius = output.blast_radius
    state.metadata["triage_summary"] = output.summary
    state.metadata["problem_area"] = output.problem_area
    state.metadata["is_real_incident"] = output.is_real_incident

    emit_event(
        state,
        "incident_opened",
        {
            "title": state.title,
            "problem_area": output.problem_area,
            "blast_radius": output.blast_radius,
            "summary": output.summary,
            "is_real_incident": output.is_real_incident,
        },
    )
    return state


def hypothesis_node(
    state: IncidentState,
    client: Optional[LLMClient] = None,
    tracker: Optional[BudgetTracker] = None,
) -> IncidentState:
    """HYPOTHESIS Node: Propose 2-5 competing root cause hypotheses with testable predictions."""
    state = ensure_incident_state(state)
    llm = client or LLMClient()

    if tracker:
        tracker.record_llm_call()
        exceeded, reason = tracker.check_and_enforce_budget(state)
        if exceeded:
            return state

    system_prompt = (
        "You are the Hypothesis Agent in Falsify SRE. "
        "Formulate 2-5 distinct, competing hypotheses explaining the failure. "
        "Do NOT commit to a single diagnosis. Assign a concrete, verifiable prediction to each hypothesis."
    )
    prompt = (
        f"Incident Title: {state.title}\n"
        f"Problem Area: {state.metadata.get('problem_area', 'unknown')}\n"
        f"Triage Summary: {state.metadata.get('triage_summary', '')}\n"
        f"Blast Radius: {state.blast_radius}\n\n"
        f"Generate competing hypotheses with predictions."
    )

    output, err = call_llm_with_one_retry(llm, prompt, HypothesisOutput, system=system_prompt)
    if output is None:
        state.errors.append(f"Hypothesis generation failed: {err}")
        state.decision = "escalate"
        return state

    new_hypotheses = []
    for item in output.hypotheses:
        hyp = Hypothesis(
            claim=item.claim,
            prediction=item.prediction,
            status="alive",
        )
        new_hypotheses.append(hyp)

    state.hypotheses = new_hypotheses
    update_state_confidence(state)

    emit_event(
        state,
        "hypotheses_proposed",
        {
            "count": len(state.hypotheses),
            "hypotheses": [
                {"id": h.id, "claim": h.claim, "prediction": h.prediction, "status": h.status}
                for h in state.hypotheses
            ],
            "confidence": state.confidence,
        },
    )
    return state


def experiment_node(
    state: IncidentState,
    client: Optional[LLMClient] = None,
    tracker: Optional[BudgetTracker] = None,
) -> IncidentState:
    """EXPERIMENT Node: Select diagnostic tool, execute experiment, and record classified evidence."""
    state = ensure_incident_state(state)
    llm = client or LLMClient()

    if tracker:
        tracker.record_tool_call()
        exceeded, reason = tracker.check_and_enforce_budget(state)
        if exceeded:
            return state

    lead = get_leading_hypothesis(state.hypotheses)
    if not lead:
        state.errors.append("Experiment failed: No active hypothesis found to test.")
        return state

    available_tools_list = list(DIAGNOSTIC_TOOLS.keys())
    system_prompt = (
        "You are the Experiment Selection Agent in Falsify SRE. "
        "Select the most appropriate diagnostic tool from the allow-list to test the leading hypothesis prediction. "
        f"Available tools: {available_tools_list}."
    )
    prompt = (
        f"Leading Hypothesis Claim: {lead.claim}\n"
        f"Prediction: {lead.prediction}\n"
        f"Available Tools: {available_tools_list}\n\n"
        f"Choose an experiment and specify tool parameters."
    )

    selection, err = call_llm_with_one_retry(llm, prompt, ExperimentSelection, system=system_prompt)
    if selection is None:
        state.errors.append(f"Experiment selection failed: {err}")
        state.decision = "escalate"
        return state

    tool_name = selection.tool_name
    if tool_name not in DIAGNOSTIC_TOOLS:
        state.errors.append(f"Selected tool '{tool_name}' is not in diagnostic allow-list {available_tools_list}")
        state.decision = "escalate"
        return state

    # Execute tool safely
    tool_func = DIAGNOSTIC_TOOLS[tool_name]
    tool_params = selection.parameters or {}
    tool_result: ToolResult = tool_func(**tool_params)

    emit_event(
        state,
        "tool_called",
        {
            "tool": tool_result.tool,
            "ok": tool_result.ok,
            "latency_ms": tool_result.latency_ms,
            "source": tool_result.source,
        },
    )

    # Evaluate tool output against hypothesis prediction
    eval_system = (
        "You are the Evidence Evaluator in Falsify SRE. "
        "Compare the tool telemetry observation with the hypothesis prediction. "
        "Classify the evidence strictly as 'supports', 'contradicts', or 'inconclusive'."
    )
    sanitized_data = sanitize_tool_output(tool_result.data)
    eval_prompt = (
        f"Hypothesis Claim: {lead.claim}\n"
        f"Hypothesis Prediction: {lead.prediction}\n"
        f"Tool Executed: {tool_result.tool} (Status OK: {tool_result.ok})\n"
        f"Observed Telemetry:\n{wrap_untrusted_context(sanitized_data, source_tag='telemetry')}\n\n"
        f"Evaluate whether this evidence supports or contradicts the prediction."
    )

    evaluation, eval_err = call_llm_with_one_retry(llm, eval_prompt, EvidenceEvaluation, system=eval_system)
    if evaluation is None:
        state.errors.append(f"Evidence evaluation failed: {eval_err}")
        state.decision = "escalate"
        return state

    # Create and record Evidence
    ev = Evidence(
        source=tool_result.source or tool_result.tool,
        claim=lead.claim,
        finding=evaluation.finding,
        classification=evaluation.classification,
        data=tool_result.data if isinstance(tool_result.data, dict) else {"raw": sanitized_data},
    )
    lead.evidence.append(ev)

    # If contradicted and no supporting evidence, mark status uncertain
    if evaluation.classification == "contradicts":
        has_support = any(e.classification == "supports" for e in lead.evidence)
        if not has_support:
            lead.status = "uncertain"

    # Deterministic confidence recalculation
    update_state_confidence(state)

    emit_event(
        state,
        "hypothesis_updated",
        {
            "hypothesis_id": lead.id,
            "claim": lead.claim,
            "status": lead.status,
            "evidence_id": ev.id,
            "classification": ev.classification,
            "finding": ev.finding,
            "confidence_after": state.confidence,
        },
    )
    return state


def skeptic_node(
    state: IncidentState,
    client: Optional[LLMClient] = None,
    tracker: Optional[BudgetTracker] = None,
) -> IncidentState:
    """SKEPTIC Node: Challenge leading hypothesis, identify evidence gaps, and prevent premature commitment."""
    state = ensure_incident_state(state)
    llm = client or LLMClient()

    if tracker:
        tracker.record_llm_call()
        exceeded, reason = tracker.check_and_enforce_budget(state)
        if exceeded:
            return state

    lead = get_leading_hypothesis(state.hypotheses)
    if not lead:
        return state

    system_prompt = (
        "You are the Skeptic Agent in Falsify SRE. Challenge the leading hypothesis aggressively. "
        "Point out potential alternate causes, weak single-signal evidence, and unverified assumptions. "
        "If the evidence is flimsy or contradicted, recommend marking it 'uncertain' or 'falsified'."
    )
    prompt = (
        f"Leading Hypothesis Claim: {lead.claim}\n"
        f"Current Status: {lead.status}\n"
        f"Evidence Gathered: {[f'{e.source} ({e.classification}): {e.finding}' for e in lead.evidence]}\n"
        f"Rival Hypotheses: {[h.claim for h in state.hypotheses if h.id != lead.id]}\n\n"
        f"Perform skeptical review."
    )

    output, err = call_llm_with_one_retry(llm, prompt, SkepticOutput, system=system_prompt)
    if output is None:
        state.errors.append(f"Skeptic review failed: {err}")
        state.decision = "escalate"
        return state

    # Apply skeptic status challenge if recommended
    if output.challenges_leading_hypothesis and output.suggested_status:
        lead.status = output.suggested_status

    # Recalculate deterministic confidence
    update_state_confidence(state)

    emit_event(
        state,
        "skeptic_note",
        {
            "critique": output.critique,
            "challenged": output.challenges_leading_hypothesis,
            "suggested_status": output.suggested_status,
            "confidence_after": state.confidence,
        },
    )
    return state


def gate_node(
    state: IncidentState,
    config: Optional[GateConfig] = None,
) -> IncidentState:
    """SAFETY GATE Node: Evaluate confidence, blast radius, ambiguity, and policy thresholds."""
    state = ensure_incident_state(state)
    cfg = config or GateConfig()

    decision = evaluate_decision_gate(state, cfg)
    state.decision = decision

    emit_event(
        state,
        "decision_made",
        {
            "decision": state.decision,
            "confidence": state.confidence,
            "blast_radius": state.blast_radius,
        },
    )
    return state


def action_node(
    state: IncidentState,
    client: Optional[LLMClient] = None,
    config: Optional[GateConfig] = None,
    tracker: Optional[BudgetTracker] = None,
) -> IncidentState:
    """ACTION Node: Select and execute explicitly allow-listed remediation action."""
    state = ensure_incident_state(state)
    llm = client or LLMClient()
    cfg = config or GateConfig()

    # Only proceed if decision was auto or approve
    if state.decision not in ("auto", "approve"):
        return state

    lead = get_leading_hypothesis(state.hypotheses)
    lead_claim = lead.claim if lead else "Unknown"

    system_prompt = (
        "You are the Remediation Action Agent in Falsify SRE. "
        "Select the appropriate remediation action from the allow-list: "
        f"{list(ALLOWED_ACTIONS)} and specify target service container name (must be a demo container)."
    )
    prompt = (
        f"Incident Title: {state.title}\n"
        f"Problem Area: {state.metadata.get('problem_area', 'unknown')}\n"
        f"Root Cause Claim: {lead_claim}\n"
        f"Allowed Actions: {list(ALLOWED_ACTIONS)}\n\n"
        f"Specify the remediation action."
    )

    selection, err = call_llm_with_one_retry(llm, prompt, ActionSelection, system=system_prompt)
    if selection is None:
        state.errors.append(f"Action selection failed: {err}")
        state.decision = "escalate"
        return state

    action_name = selection.action_name
    params = selection.parameters or {}

    # Safety Gate Action Validation
    is_valid, reason = validate_action_execution(action_name, params, state, cfg)
    if not is_valid:
        state.errors.append(f"Action rejected by safety gate: {reason}")
        state.decision = "escalate"
        return state

    if action_name not in REMEDIATION_TOOLS:
        state.errors.append(f"Action '{action_name}' tool function not found in remediation registry.")
        state.decision = "escalate"
        return state

    # Execute allow-listed action
    tool_func = REMEDIATION_TOOLS[action_name]
    tool_result: ToolResult = tool_func(**params)

    if tracker:
        tracker.record_tool_call()

    state.actions_taken.append({
        "action": tool_result.tool,
        "ok": tool_result.ok,
        "parameters": params,
        "result": tool_result.data,
        "timestamp": time.time(),
    })

    emit_event(
        state,
        "action_taken",
        {
            "action": tool_result.tool,
            "ok": tool_result.ok,
            "parameters": params,
            "latency_ms": tool_result.latency_ms,
            "result": tool_result.data,
        },
    )
    return state


def verify_node(
    state: IncidentState,
    client: Optional[LLMClient] = None,
    tracker: Optional[BudgetTracker] = None,
) -> IncidentState:
    """VERIFICATION Node: Verify post-remediation system recovery."""
    state = ensure_incident_state(state)
    llm = client or LLMClient()

    if not state.actions_taken:
        # No action was taken to verify
        return state

    last_action = state.actions_taken[-1]

    system_prompt = (
        "You are the Verification Agent in Falsify SRE. "
        "Examine the executed remediation action and telemetry to verify whether the incident is resolved."
    )
    prompt = (
        f"Incident Title: {state.title}\n"
        f"Last Action Taken: {last_action}\n"
        f"Telemetry: Post-action healthchecks passing.\n\n"
        f"Evaluate recovery status."
    )

    output, err = call_llm_with_one_retry(llm, prompt, VerificationOutput, system=system_prompt)
    if output is None:
        state.errors.append(f"Verification evaluation failed: {err}")
        state.decision = "escalate"
        return state

    if output.recovered:
        state.status = "resolved"
        emit_event(
            state,
            "recovery_checked",
            {
                "recovered": True,
                "finding": output.finding,
                "action": last_action["action"],
            },
        )
        emit_event(
            state,
            "incident_closed",
            {
                "status": "resolved",
                "actions_count": len(state.actions_taken),
                "iterations": state.iterations,
            },
        )
    else:
        state.iterations += 1
        if tracker:
            tracker.record_iteration()

        emit_event(
            state,
            "recovery_checked",
            {
                "recovered": False,
                "finding": output.finding,
                "iteration": state.iterations,
            },
        )

        max_iter = tracker.config.max_iterations if tracker else 3
        if state.iterations >= max_iter:
            state.decision = "escalate"
            state.status = "escalated"
            state.errors.append(f"Recovery failed after {state.iterations} iterations. Escalated to human SRE.")
        else:
            state.decision = "escalate"

    return state


def memory_node(state: IncidentState) -> IncidentState:
    """Memory node: Store resolved incident details into memory store (Phase A5 Stub)."""
    emit_event(
        state,
        "memory_saved",
        {
            "incident_id": state.incident_id,
            "status": state.status,
            "hypotheses_count": len(state.hypotheses),
        },
    )
    return state


# =====================================================================
# LangGraph Workflow Graph Builder & Conditional Routing
# =====================================================================

def route_after_gate(state: IncidentState) -> str:
    """Conditional routing based on safety decision gate outcome."""
    if state.decision in ("auto", "approve"):
        return "action"
    return END


def build_incident_graph(
    client: Optional[LLMClient] = None,
    gate_config: Optional[GateConfig] = None,
    budget_tracker: Optional[BudgetTracker] = None,
) -> Any:
    """Construct and compile the complete LangGraph agent reasoning and safety workflow:
    
    Flow:
      START -> triage -> hypothesis -> experiment -> skeptic -> gate
            -> (auto/approve) -> action -> verify -> END
            -> (escalate) -> END
    """
    builder = StateGraph(IncidentState)
    llm = client or LLMClient()
    gate_cfg = gate_config or GateConfig()
    budget = budget_tracker

    builder.add_node("triage", lambda s: triage_node(s, client=llm, tracker=budget))
    builder.add_node("hypothesis", lambda s: hypothesis_node(s, client=llm, tracker=budget))
    builder.add_node("experiment", lambda s: experiment_node(s, client=llm, tracker=budget))
    builder.add_node("skeptic", lambda s: skeptic_node(s, client=llm, tracker=budget))
    builder.add_node("gate", lambda s: gate_node(s, config=gate_cfg))
    builder.add_node("action", lambda s: action_node(s, client=llm, config=gate_cfg, tracker=budget))
    builder.add_node("verify", lambda s: verify_node(s, client=llm, tracker=budget))

    builder.add_edge(START, "triage")
    builder.add_edge("triage", "hypothesis")
    builder.add_edge("hypothesis", "experiment")
    builder.add_edge("experiment", "skeptic")
    builder.add_edge("skeptic", "gate")

    # Conditional branching at Gate
    builder.add_conditional_edges(
        "gate",
        route_after_gate,
        {
            "action": "action",
            END: END,
        },
    )
    builder.add_edge("action", "verify")
    builder.add_edge("verify", END)

    return builder.compile()
