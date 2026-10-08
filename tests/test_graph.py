"""Comprehensive tests for LangGraph agent nodes, safety gate, action, verification, and budget limits."""

import json
import pytest
from falsify.budget import BudgetConfig, BudgetTracker
from falsify.confidence import CAP_FEWER_THAN_TWO_SOURCES
from falsify.gate import GateConfig
from falsify.graph import (
    DIAGNOSTIC_TOOLS,
    REMEDIATION_TOOLS,
    action_node,
    build_incident_graph,
    call_llm_with_one_retry,
    experiment_node,
    gate_node,
    hypothesis_node,
    skeptic_node,
    triage_node,
    verify_node,
    TriageOutput,
)
from falsify.llm import LLMClient, LLMConfig
from falsify.state import Evidence, Hypothesis, IncidentState


def test_triage_node_standalone(tmp_path):
    """Verify Triage node extracts summary, problem area, blast radius, and emits incident_opened event."""
    db_file = str(tmp_path / "cache.sqlite")

    def triage_mock_caller(model, system, prompt, json_mode):
        return json.dumps({
            "summary": "High latency and 500 error spike on /checkout",
            "problem_area": "payment-service",
            "blast_radius": "high",
            "is_real_incident": True,
        })

    client = LLMClient(LLMConfig(cache_db_path=db_file), custom_caller=triage_mock_caller)
    state = IncidentState(title="Alert: Checkout Latency High", metadata={"service": "payment"})

    updated_state = triage_node(state, client=client)

    assert updated_state.blast_radius == "high"
    assert updated_state.metadata["problem_area"] == "payment-service"
    assert updated_state.metadata["triage_summary"] == "High latency and 500 error spike on /checkout"

    # Verify event emission
    assert len(updated_state.events) == 1
    event = updated_state.events[0]
    assert event["type"] == "incident_opened"
    assert event["payload"]["problem_area"] == "payment-service"
    assert event["payload"]["blast_radius"] == "high"


def test_hypothesis_node_competing_hypotheses(tmp_path):
    """Verify Hypothesis node generates multiple competing hypotheses and calculates initial confidence."""
    db_file = str(tmp_path / "cache.sqlite")

    def hyp_mock_caller(model, system, prompt, json_mode):
        return json.dumps({
            "hypotheses": [
                {
                    "claim": "Database connection pool exhausted",
                    "prediction": "Active db connections equal max limit",
                },
                {
                    "claim": "Upstream payment provider outage",
                    "prediction": "Probe to payment gateway returns 504",
                },
                {
                    "claim": "Memory leak causing high GC pauses",
                    "prediction": "Memory usage near 100% and GC duration elevated",
                },
            ]
        })

    client = LLMClient(LLMConfig(cache_db_path=db_file), custom_caller=hyp_mock_caller)
    state = IncidentState(title="Payment degradation")

    updated_state = hypothesis_node(state, client=client)

    assert len(updated_state.hypotheses) == 3
    assert all(h.status == "alive" for h in updated_state.hypotheses)
    assert updated_state.hypotheses[0].claim == "Database connection pool exhausted"
    assert updated_state.confidence <= 0.20  # Initial confidence capped before evidence

    # Verify hypotheses_proposed event
    assert len(updated_state.events) == 1
    event = updated_state.events[0]
    assert event["type"] == "hypotheses_proposed"
    assert event["payload"]["count"] == 3


def test_experiment_node_tool_execution(tmp_path):
    """Verify Experiment node selects tool, executes tool safely, and records classified evidence."""
    db_file = str(tmp_path / "cache.sqlite")

    call_count = 0

    def experiment_mock_caller(model, system, prompt, json_mode):
        nonlocal call_count
        call_count += 1
        if "Available Tools" in prompt:
            # Tool selection step
            return json.dumps({
                "hypothesis_claim": "Database connection pool exhausted",
                "tool_name": "get_db_stats",
                "parameters": {"db_identifier": "payment-db"},
                "expected_observation": "active_connections == max_connections",
            })
        else:
            # Evidence evaluation step
            return json.dumps({
                "classification": "supports",
                "finding": "DB connection count at max capacity",
            })

    client = LLMClient(LLMConfig(cache_db_path=db_file), custom_caller=experiment_mock_caller)
    hyp = Hypothesis(
        claim="Database connection pool exhausted",
        prediction="Active db connections equal max limit",
        status="alive",
    )
    state = IncidentState(hypotheses=[hyp])

    updated_state = experiment_node(state, client=client)

    assert len(hyp.evidence) == 1
    ev = hyp.evidence[0]
    assert ev.classification == "supports"
    assert ev.source == "db_stub"
    assert updated_state.confidence > 0.20
    assert updated_state.confidence <= CAP_FEWER_THAN_TWO_SOURCES

    # Verify tool_called and hypothesis_updated events
    event_types = [e["type"] for e in updated_state.events]
    assert "tool_called" in event_types
    assert "hypothesis_updated" in event_types


def test_experiment_node_disallows_unapproved_tool(tmp_path):
    """Verify Experiment node rejects tools outside the allowed diagnostic registry."""
    db_file = str(tmp_path / "cache.sqlite")

    def unapproved_tool_caller(model, system, prompt, json_mode):
        return json.dumps({
            "hypothesis_claim": "Hacked container",
            "tool_name": "delete_all_files",
            "parameters": {},
            "expected_observation": "files deleted",
        })

    client = LLMClient(LLMConfig(cache_db_path=db_file), custom_caller=unapproved_tool_caller)
    hyp = Hypothesis(claim="Hacked container", prediction="files compromised")
    state = IncidentState(hypotheses=[hyp])

    updated_state = experiment_node(state, client=client)

    assert updated_state.decision == "escalate"
    assert any("not in diagnostic allow-list" in err for err in updated_state.errors)
    assert len(hyp.evidence) == 0  # No tool executed


def test_skeptic_node_challenges_leading_hypothesis(tmp_path):
    """Verify Skeptic node can challenge leading hypothesis and demote status."""
    db_file = str(tmp_path / "cache.sqlite")

    def skeptic_mock_caller(model, system, prompt, json_mode):
        return json.dumps({
            "critique": "Single metric spike could be a transient probe artifact; no log errors observed.",
            "challenges_leading_hypothesis": True,
            "suggested_status": "uncertain",
            "rival_to_promote_claim": "Transient network blip",
        })

    client = LLMClient(LLMConfig(cache_db_path=db_file), custom_caller=skeptic_mock_caller)
    ev = Evidence(source="metrics", claim="DB pool full", finding="spike", classification="supports")
    hyp = Hypothesis(claim="DB pool full", prediction="spike", status="alive", evidence=[ev])
    state = IncidentState(hypotheses=[hyp])

    updated_state = skeptic_node(state, client=client)

    assert hyp.status == "uncertain"
    assert len(updated_state.events) == 1
    assert updated_state.events[0]["type"] == "skeptic_note"
    assert updated_state.events[0]["payload"]["challenged"] is True


def test_malformed_llm_output_retried_once_and_succeeds(tmp_path):
    """Verify malformed JSON on first attempt triggers ONE retry and succeeds on second attempt."""
    db_file = str(tmp_path / "cache.sqlite")
    attempts = 0

    def flaky_caller(model, system, prompt, json_mode):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return "This is completely malformed text and not JSON"
        return json.dumps({
            "summary": "Recovered triage summary",
            "problem_area": "auth-service",
            "blast_radius": "low",
            "is_real_incident": True,
        })

    client = LLMClient(LLMConfig(cache_db_path=db_file), custom_caller=flaky_caller)
    parsed, err = call_llm_with_one_retry(client, "Do triage", TriageOutput)

    assert attempts == 2
    assert err is None
    assert parsed is not None
    assert parsed.problem_area == "auth-service"


def test_second_malformed_output_safe_escalation(tmp_path):
    """Verify node safely escalates when LLM response remains malformed after retry."""
    db_file = str(tmp_path / "cache.sqlite")

    def persistent_malformed_caller(model, system, prompt, json_mode):
        return "Not valid JSON at all"

    client = LLMClient(LLMConfig(cache_db_path=db_file), custom_caller=persistent_malformed_caller)
    state = IncidentState(title="Alert: API error rate")

    updated_state = triage_node(state, client=client)

    assert updated_state.decision == "escalate"
    assert len(updated_state.errors) >= 1
    assert "Triage failed" in updated_state.errors[0]
    # Verify no fake events or fake data invented
    assert len(updated_state.events) == 0


def test_action_node_allowed_action_execution(tmp_path):
    """Verify Action node selects and executes allow-listed action when decision is auto."""
    db_file = str(tmp_path / "cache.sqlite")

    def action_mock_caller(model, system, prompt, json_mode):
        return json.dumps({
            "action_name": "restart_service",
            "parameters": {"service_name": "falsify-demo-payment"},
            "rationale": "Clear corrupted memory state in payment container",
        })

    client = LLMClient(LLMConfig(cache_db_path=db_file), custom_caller=action_mock_caller)
    ev = Evidence(source="metrics", claim="Bug", finding="err", classification="supports")
    hyp = Hypothesis(claim="Bug", prediction="err", status="alive", evidence=[ev])
    state = IncidentState(
        title="Payment Crash",
        decision="auto",
        confidence=0.85,
        hypotheses=[hyp],
    )

    updated_state = action_node(state, client=client)

    assert len(updated_state.actions_taken) == 1
    action_rec = updated_state.actions_taken[0]
    assert action_rec["action"] == "restart_service"
    assert action_rec["parameters"] == {"service_name": "falsify-demo-payment"}

    # Verify action_taken event emission
    event_types = [e["type"] for e in updated_state.events]
    assert "action_taken" in event_types


def test_action_node_rejects_unsafe_action_and_escalates(tmp_path):
    """Verify Action node rejects unsafe action suggested by LLM and escalates without executing."""
    db_file = str(tmp_path / "cache.sqlite")

    def unsafe_action_caller(model, system, prompt, json_mode):
        return json.dumps({
            "action_name": "delete_database",
            "parameters": {"db": "all"},
            "rationale": "Clear everything",
        })

    client = LLMClient(LLMConfig(cache_db_path=db_file), custom_caller=unsafe_action_caller)
    state = IncidentState(title="Outage", decision="auto", confidence=0.85)

    updated_state = action_node(state, client=client)

    assert updated_state.decision == "escalate"
    assert len(updated_state.actions_taken) == 0
    assert any("Action rejected by safety gate" in err for err in updated_state.errors)


def test_verify_node_successful_recovery(tmp_path):
    """Verify Verify node detects recovery, sets status to resolved, and emits closed event."""
    db_file = str(tmp_path / "cache.sqlite")

    def verify_mock_caller(model, system, prompt, json_mode):
        return json.dumps({
            "recovered": True,
            "finding": "Container healthy, error rate dropped to 0%, HTTP 200 returned.",
        })

    client = LLMClient(LLMConfig(cache_db_path=db_file), custom_caller=verify_mock_caller)
    state = IncidentState(
        title="Payment Service Down",
        status="investigating",
        actions_taken=[{"action": "restart_service", "ok": True}],
    )

    updated_state = verify_node(state, client=client)

    assert updated_state.status == "resolved"
    event_types = [e["type"] for e in updated_state.events]
    assert "recovery_checked" in event_types
    assert "incident_closed" in event_types


def test_verify_node_failed_recovery_escalates_without_blind_repeat(tmp_path):
    """Verify Verify node increments iterations and escalates on failed verification without repeating actions."""
    db_file = str(tmp_path / "cache.sqlite")

    def failed_verify_caller(model, system, prompt, json_mode):
        return json.dumps({
            "recovered": False,
            "finding": "Service still returning HTTP 500 error after restart.",
        })

    client = LLMClient(LLMConfig(cache_db_path=db_file), custom_caller=failed_verify_caller)
    tracker = BudgetTracker(config=BudgetConfig(max_iterations=3))
    state = IncidentState(
        title="Persistent Error",
        status="investigating",
        iterations=0,
        actions_taken=[{"action": "restart_service", "ok": True}],
    )

    updated_state = verify_node(state, client=client, tracker=tracker)

    assert updated_state.iterations == 1
    assert updated_state.decision == "escalate"
    event_types = [e["type"] for e in updated_state.events]
    assert "recovery_checked" in event_types
    assert "incident_closed" not in event_types


def test_verify_node_escalation_after_max_iterations(tmp_path):
    """Verify Verify node permanently escalates to human SRE when max iterations are exhausted."""
    db_file = str(tmp_path / "cache.sqlite")

    def failed_verify_caller(model, system, prompt, json_mode):
        return json.dumps({
            "recovered": False,
            "finding": "Repeated failure to recover.",
        })

    client = LLMClient(LLMConfig(cache_db_path=db_file), custom_caller=failed_verify_caller)
    tracker = BudgetTracker(config=BudgetConfig(max_iterations=3))
    state = IncidentState(
        title="Persistent Error",
        status="investigating",
        iterations=2,  # Already at 2 iterations
        actions_taken=[{"action": "rollback_deploy", "ok": True}],
    )

    updated_state = verify_node(state, client=client, tracker=tracker)

    assert updated_state.iterations == 3
    assert updated_state.decision == "escalate"
    assert updated_state.status == "escalated"
    assert any("Recovery failed after 3 iterations" in err for err in updated_state.errors)


def test_full_graph_orchestration_flow(tmp_path):
    """Verify full LangGraph flow: START -> triage -> hypothesis -> experiment -> skeptic -> gate -> action -> verify -> END."""
    db_file = str(tmp_path / "cache.sqlite")

    def comprehensive_mock_caller(model, system, prompt, json_mode):
        sys_str = system or ""
        if "Triage Agent" in sys_str:
            return json.dumps({
                "summary": "Elevated 500 error rate on checkout endpoint",
                "problem_area": "payment-service",
                "blast_radius": "low",
                "is_real_incident": True,
            })
        elif "Hypothesis Agent" in sys_str:
            return json.dumps({
                "hypotheses": [
                    {
                        "claim": "Database connection pool exhausted",
                        "prediction": "Active db connections equal max limit",
                    },
                    {
                        "claim": "Upstream gateway network timeout",
                        "prediction": "Probe to gateway returns 504",
                    },
                ]
            })
        elif "Experiment Selection Agent" in sys_str:
            return json.dumps({
                "hypothesis_claim": "Database connection pool exhausted",
                "tool_name": "get_db_stats",
                "parameters": {"db_identifier": "payment-db"},
                "expected_observation": "active_connections == max_connections",
            })
        elif "Evidence Evaluator" in sys_str:
            return json.dumps({
                "classification": "supports",
                "finding": "DB connection count at 100/100 capacity",
            })
        elif "Skeptic Agent" in sys_str:
            return json.dumps({
                "critique": "Evidence is consistent with pool exhaustion.",
                "challenges_leading_hypothesis": False,
                "suggested_status": None,
            })
        elif "Remediation Action Agent" in sys_str:
            return json.dumps({
                "action_name": "restart_service",
                "parameters": {"service_name": "falsify-demo-payment"},
                "rationale": "Restart container to reset pool connections",
            })
        elif "Verification Agent" in sys_str:
            return json.dumps({
                "recovered": True,
                "finding": "Service healthchecks 200 OK after restart.",
            })
        return "{}"

    client = LLMClient(LLMConfig(cache_db_path=db_file), custom_caller=comprehensive_mock_caller)
    # Configure auto_threshold low enough for single-source demo or multi-source
    gate_cfg = GateConfig(auto_threshold=0.40, approve_threshold=0.30)
    graph = build_incident_graph(client=client, gate_config=gate_cfg)

    initial_state = IncidentState(title="Checkout Error Spike", metadata={"env": "demo"})
    result = graph.invoke(initial_state)

    # Convert back to IncidentState
    final_state = IncidentState.model_validate(result)

    assert final_state.blast_radius == "low"
    assert final_state.metadata["problem_area"] == "payment-service"
    assert len(final_state.hypotheses) == 2
    assert final_state.hypotheses[0].claim == "Database connection pool exhausted"
    assert len(final_state.hypotheses[0].evidence) == 1
    assert final_state.decision == "auto"
    assert len(final_state.actions_taken) == 1
    assert final_state.actions_taken[0]["action"] == "restart_service"
    assert final_state.status == "resolved"

    # Verify complete audit timeline event sequence
    event_types = [e["type"] for e in final_state.events]
    assert event_types == [
        "incident_opened",
        "hypotheses_proposed",
        "tool_called",
        "hypothesis_updated",
        "skeptic_note",
        "decision_made",
        "action_taken",
        "recovery_checked",
        "incident_closed",
    ]
