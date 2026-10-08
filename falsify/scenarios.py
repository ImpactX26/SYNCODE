"""Deterministic end-to-end scenario fixtures and runner for Falsify."""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Optional

from falsify.budget import BudgetConfig, BudgetTracker
from falsify.confidence import get_leading_hypothesis
from falsify.gate import GateConfig
from falsify.graph import build_incident_graph
from falsify.llm import LLMClient, LLMConfig
from falsify.memory import IncidentMemoryStore
from falsify.state import IncidentState


def _bad_deploy_caller(model: str, system: Optional[str], prompt: str, json_mode: bool) -> str:
    """Mock LLM caller for Scenario 1: bad_deploy."""
    sys_str = system or ""
    if "Triage Agent" in sys_str:
        return json.dumps({
            "summary": "Elevated HTTP 500 error rate on payment-service immediately following release v1.2.4",
            "problem_area": "payment-service",
            "blast_radius": "low",
            "is_real_incident": True,
        })
    elif "Hypothesis Agent" in sys_str:
        return json.dumps({
            "hypotheses": [
                {
                    "claim": "Faulty deployment v1.2.4 introduced regression in payment-service",
                    "prediction": "Deploy history shows release v1.2.4 and logs show NullPointerException",
                },
                {
                    "claim": "Database connection pool exhausted",
                    "prediction": "Active DB connections at 100/100",
                },
                {
                    "claim": "External gateway network partition",
                    "prediction": "Network probe returns 504",
                },
            ]
        })
    elif "Experiment Selection Agent" in sys_str:
        return json.dumps({
            "hypothesis_claim": "Faulty deployment v1.2.4 introduced regression in payment-service",
            "tool_name": "get_deploy_history",
            "parameters": {"service_name": "falsify-demo-payment", "limit": 5},
            "expected_observation": "Recent deployment of v1.2.4",
        })
    elif "Evidence Evaluator" in sys_str:
        return json.dumps({
            "classification": "supports",
            "finding": "Deploy history confirms v1.2.4 release 5m ago and logs show recurring NullPointerException on checkout.",
        })
    elif "Skeptic Agent" in sys_str:
        return json.dumps({
            "critique": "Evidence corroborates regression in v1.2.4 release. Competing causes lack supporting signals.",
            "challenges_leading_hypothesis": False,
            "suggested_status": None,
        })
    elif "Remediation Action Agent" in sys_str:
        return json.dumps({
            "action_name": "rollback_deploy",
            "parameters": {"service_name": "falsify-demo-payment", "target_version": "v1.2.3"},
            "rationale": "Roll back to previous stable release v1.2.3",
        })
    elif "Verification Agent" in sys_str:
        return json.dumps({
            "recovered": True,
            "finding": "Telemetry confirms error rate returned to nominal 0.01% post-rollback to v1.2.3.",
        })
    return "{}"


def _db_pool_exhaustion_caller(model: str, system: Optional[str], prompt: str, json_mode: bool) -> str:
    """Mock LLM caller for Scenario 2: db_pool_exhaustion."""
    sys_str = system or ""
    if "Triage Agent" in sys_str:
        return json.dumps({
            "summary": "Database connection saturation causing HTTP 503 errors and request timeouts on checkout",
            "problem_area": "payment-db",
            "blast_radius": "medium",
            "is_real_incident": True,
        })
    elif "Hypothesis Agent" in sys_str:
        return json.dumps({
            "hypotheses": [
                {
                    "claim": "Database connection pool saturated in payment-db",
                    "prediction": "get_db_stats active_connections == max_connections (100/100)",
                },
                {
                    "claim": "Memory leak in payment-service container",
                    "prediction": "get_metrics memory > 95%",
                },
                {
                    "claim": "Downstream dependency timeout",
                    "prediction": "probe_dependency latency > 3000ms",
                },
            ]
        })
    elif "Experiment Selection Agent" in sys_str:
        return json.dumps({
            "hypothesis_claim": "Database connection pool saturated in payment-db",
            "tool_name": "get_db_stats",
            "parameters": {"db_identifier": "falsify-demo-db"},
            "expected_observation": "Active connections equal max_connections",
        })
    elif "Evidence Evaluator" in sys_str:
        return json.dumps({
            "classification": "supports",
            "finding": "DB stats confirm 100/100 active connections saturated with 48 threads waiting.",
        })
    elif "Skeptic Agent" in sys_str:
        return json.dumps({
            "critique": "Strong multi-signal corroboration of connection pool exhaustion.",
            "challenges_leading_hypothesis": False,
            "suggested_status": None,
        })
    elif "Remediation Action Agent" in sys_str:
        return json.dumps({
            "action_name": "restart_service",
            "parameters": {"service_name": "falsify-demo-payment"},
            "rationale": "Restart container to reset pool connections and release leaked handles",
        })
    elif "Verification Agent" in sys_str:
        return json.dumps({
            "recovered": True,
            "finding": "Database active connections dropped to 12/100 and HTTP 503 errors eliminated.",
        })
    return "{}"


def _slow_dependency_caller(model: str, system: Optional[str], prompt: str, json_mode: bool) -> str:
    """Mock LLM caller for Scenario 3: slow_dependency."""
    sys_str = system or ""
    if "Triage Agent" in sys_str:
        return json.dumps({
            "summary": "Severe downstream dependency latency causing cascading slowdown on order checkout",
            "problem_area": "inventory-service",
            "blast_radius": "medium",
            "is_real_incident": True,
        })
    elif "Hypothesis Agent" in sys_str:
        return json.dumps({
            "hypotheses": [
                {
                    "claim": "Downstream inventory service dependency high latency",
                    "prediction": "probe_dependency latency > 1500ms",
                },
                {
                    "claim": "Gateway worker thread pool exhaustion",
                    "prediction": "get_metrics gateway CPU > 95%",
                },
                {
                    "claim": "Database table lock contention",
                    "prediction": "get_db_stats lock_wait_count > 50",
                },
            ]
        })
    elif "Experiment Selection Agent" in sys_str:
        return json.dumps({
            "hypothesis_claim": "Downstream inventory service dependency high latency",
            "tool_name": "probe_dependency",
            "parameters": {"target_url": "http://inventory-service:8080/health", "timeout_sec": 2.0},
            "expected_observation": "Probe latency > 1500ms",
        })
    elif "Evidence Evaluator" in sys_str:
        return json.dumps({
            "classification": "supports",
            "finding": "Dependency probe to inventory-service measured 2100ms latency (threshold 200ms).",
        })
    elif "Skeptic Agent" in sys_str:
        return json.dumps({
            "critique": "Confirmed dependency latency on inventory service. Scaling replicas will alleviate queueing bottleneck.",
            "challenges_leading_hypothesis": False,
            "suggested_status": None,
        })
    elif "Remediation Action Agent" in sys_str:
        return json.dumps({
            "action_name": "scale_service",
            "parameters": {"service_name": "falsify-demo-inventory", "replicas": 3},
            "rationale": "Scale inventory service to 3 replicas to distribute load",
        })
    elif "Verification Agent" in sys_str:
        return json.dumps({
            "recovered": True,
            "finding": "Inventory service scaled to 3 replicas, downstream latency dropped to 45ms, P99 latency resolved.",
        })
    return "{}"


def _false_alarm_caller(model: str, system: Optional[str], prompt: str, json_mode: bool) -> str:
    """Mock LLM caller for Scenario 4: false_alarm."""
    sys_str = system or ""
    if "Triage Agent" in sys_str:
        return json.dumps({
            "summary": "Transient synthetic test probe spike reported by monitoring; service operating normally",
            "problem_area": "gateway",
            "blast_radius": "low",
            "is_real_incident": False,
        })
    elif "Hypothesis Agent" in sys_str:
        return json.dumps({
            "hypotheses": [
                {
                    "claim": "Gateway container failure",
                    "prediction": "get_logs shows fatal 500 error logs and restart count > 0",
                },
                {
                    "claim": "Synthetic benchmark test probe traffic (False Alarm)",
                    "prediction": "get_metrics error rate nominal and logs show 200 OK",
                },
            ]
        })
    elif "Experiment Selection Agent" in sys_str:
        return json.dumps({
            "hypothesis_claim": "Gateway container failure",
            "tool_name": "get_logs",
            "parameters": {"service_name": "falsify-demo-gateway", "lines": 50},
            "expected_observation": "Fatal error logs present",
        })
    elif "Evidence Evaluator" in sys_str:
        return json.dumps({
            "classification": "contradicts",
            "finding": "Gateway logs show 100% successful HTTP 200 responses with zero crash/error logs.",
        })
    elif "Skeptic Agent" in sys_str:
        return json.dumps({
            "critique": "FALSE ALARM CONFIRMED: Gateway healthchecks and logs confirm nominal operation. Zero failure evidence. DO NOT RESTART OR ROLLBACK.",
            "challenges_leading_hypothesis": True,
            "suggested_status": "falsified",
        })
    return "{}"


def _ambiguous_caller(model: str, system: Optional[str], prompt: str, json_mode: bool) -> str:
    """Mock LLM caller for Scenario 5: ambiguous."""
    sys_str = system or ""
    if "Triage Agent" in sys_str:
        return json.dumps({
            "summary": "Distributed intermittent failure symptoms across gateway, payment, and database",
            "problem_area": "distributed-mesh",
            "blast_radius": "high",
            "is_real_incident": True,
        })
    elif "Hypothesis Agent" in sys_str:
        return json.dumps({
            "hypotheses": [
                {
                    "claim": "Service mesh DNS resolution failure",
                    "prediction": "get_logs shows DNS timeout warnings",
                },
                {
                    "claim": "Intermittent database socket drops",
                    "prediction": "get_db_stats shows socket read timeouts",
                },
                {
                    "claim": "TLS certificate expiration on internal proxy",
                    "prediction": "probe_dependency returns SSL error",
                },
            ]
        })
    elif "Experiment Selection Agent" in sys_str:
        return json.dumps({
            "hypothesis_claim": "Service mesh DNS resolution failure",
            "tool_name": "get_logs",
            "parameters": {"service_name": "falsify-demo-gateway", "pattern": "DNS"},
            "expected_observation": "DNS warning logs",
        })
    elif "Evidence Evaluator" in sys_str:
        return json.dumps({
            "classification": "inconclusive",
            "finding": "Single DNS warning line observed; insufficient to conclude mesh DNS outage.",
        })
    elif "Skeptic Agent" in sys_str:
        return json.dumps({
            "critique": "HIGH RISK AMBIGUITY: Multiple competing hypotheses have weak, inconclusive evidence. No hypothesis is proven or falsified. Blind remediation is unsafe.",
            "challenges_leading_hypothesis": True,
            "suggested_status": "uncertain",
        })
    return "{}"


SCENARIO_CALLERS: Dict[str, Callable[[str, Optional[str], str, bool], str]] = {
    "bad_deploy": _bad_deploy_caller,
    "db_pool_exhaustion": _db_pool_exhaustion_caller,
    "slow_dependency": _slow_dependency_caller,
    "false_alarm": _false_alarm_caller,
    "ambiguous": _ambiguous_caller,
}

SCENARIO_INITIAL_STATES: Dict[str, Dict[str, Any]] = {
    "bad_deploy": {
        "title": "High HTTP 500 error spike on /checkout after v1.2.4 release",
        "status": "investigating",
        "blast_radius": "low",
        "metadata": {"service": "payment-service", "version": "v1.2.4"},
    },
    "db_pool_exhaustion": {
        "title": "High HTTP 503 and latency degradation on checkout flow",
        "status": "investigating",
        "blast_radius": "medium",
        "metadata": {"service": "payment-db"},
    },
    "slow_dependency": {
        "title": "P99 latency degradation on gateway /api/v1/orders",
        "status": "investigating",
        "blast_radius": "medium",
        "metadata": {"service": "inventory-service"},
    },
    "false_alarm": {
        "title": "Spike in metric alert: gateway error rate reported at 12%",
        "status": "investigating",
        "blast_radius": "low",
        "metadata": {"service": "gateway"},
    },
    "ambiguous": {
        "title": "Intermittent 502 Bad Gateway and connection drops across multiple endpoints",
        "status": "investigating",
        "blast_radius": "high",
        "metadata": {"problem_area": "distributed-mesh"},
    },
}


def get_scenario_initial_state(scenario_id: str) -> IncidentState:
    """Return initial IncidentState for a given scenario."""
    if scenario_id not in SCENARIO_INITIAL_STATES:
        raise ValueError(f"Unknown scenario ID '{scenario_id}'. Allowed: {list(SCENARIO_INITIAL_STATES.keys())}")
    return IncidentState.model_validate(SCENARIO_INITIAL_STATES[scenario_id])


def create_scenario_llm_client(scenario_id: str, cache_db_path: str = ":memory:") -> LLMClient:
    """Create an LLMClient configured with deterministic mock caller for a given scenario."""
    if scenario_id not in SCENARIO_CALLERS:
        raise ValueError(f"Unknown scenario ID '{scenario_id}'. Allowed: {list(SCENARIO_CALLERS.keys())}")
    caller = SCENARIO_CALLERS[scenario_id]
    config = LLMConfig(cache_db_path=cache_db_path, replay_mode=False)
    return LLMClient(config=config, custom_caller=caller)


def run_scenario_e2e(
    scenario_id: str,
    gate_config: Optional[GateConfig] = None,
    budget_tracker: Optional[BudgetTracker] = None,
    memory_store: Optional[IncidentMemoryStore] = None,
) -> IncidentState:
    """Run an end-to-end deterministic scenario through the compiled LangGraph workflow."""
    initial_state = get_scenario_initial_state(scenario_id)
    client = create_scenario_llm_client(scenario_id)
    
    # Auto threshold: 0.40 is sufficient for single-experiment demo corroboration
    gate_cfg = gate_config or GateConfig(auto_threshold=0.40, approve_threshold=0.30)
    tracker = budget_tracker or BudgetTracker(config=BudgetConfig(max_iterations=3))
    
    graph = build_incident_graph(
        client=client,
        gate_config=gate_cfg,
        budget_tracker=tracker,
    )
    
    result = graph.invoke(initial_state)
    final_state = IncidentState.model_validate(result)

    # Save to memory if store is provided
    if memory_store:
        memory_store.save_incident(final_state)

    return final_state
