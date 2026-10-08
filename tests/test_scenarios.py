"""End-to-end deterministic tests for all 5 Falsify incident scenarios."""

import pytest
from falsify.gate import GateConfig
from falsify.memory import IncidentMemoryStore
from falsify.scenarios import (
    SCENARIO_INITIAL_STATES,
    get_scenario_initial_state,
    run_scenario_e2e,
)
from falsify.state import IncidentState


def test_scenario_initial_states():
    """Verify all 5 scenario initial states are defined and valid."""
    assert len(SCENARIO_INITIAL_STATES) == 5
    for name in ["bad_deploy", "db_pool_exhaustion", "slow_dependency", "false_alarm", "ambiguous"]:
        state = get_scenario_initial_state(name)
        assert isinstance(state, IncidentState)
        assert state.incident_id.startswith("inc_")
        assert state.status == "investigating"


def test_scenario_bad_deploy_e2e(tmp_path):
    """Scenario 1: bad_deploy
    - diagnose bad deployment regression
    - execute allowed rollback_deploy action
    - verify recovery
    """
    mem_file = str(tmp_path / "memory.sqlite")
    memory_store = IncidentMemoryStore(db_path=mem_file)

    final_state = run_scenario_e2e("bad_deploy", memory_store=memory_store)

    # 1. Diagnosed bad deployment
    assert final_state.metadata["problem_area"] == "payment-service"
    lead = final_state.hypotheses[0]
    assert "Faulty deployment" in lead.claim
    assert len(lead.evidence) >= 1
    assert lead.evidence[0].classification == "supports"

    # 2. Performed allowed rollback action
    assert final_state.decision == "auto"
    assert len(final_state.actions_taken) == 1
    action = final_state.actions_taken[0]
    assert action["action"] == "rollback_deploy"
    assert action["parameters"]["target_version"] == "v1.2.3"
    assert action["ok"] is True

    # 3. Verified recovery
    assert final_state.status == "resolved"

    # 4. Memory saved
    records = memory_store.find_similar_incidents("bad_deploy")
    assert len(records) == 1
    assert records[0].verified is True
    assert records[0].remediation_action == "rollback_deploy"


def test_scenario_db_pool_exhaustion_e2e(tmp_path):
    """Scenario 2: db_pool_exhaustion
    - identify DB pool exhaustion
    - execute allowed restart_service action
    - verify recovery
    """
    mem_file = str(tmp_path / "memory.sqlite")
    memory_store = IncidentMemoryStore(db_path=mem_file)

    final_state = run_scenario_e2e("db_pool_exhaustion", memory_store=memory_store)

    # 1. Identified DB pool exhaustion
    assert final_state.metadata["problem_area"] == "payment-db"
    lead = final_state.hypotheses[0]
    assert "Database connection pool" in lead.claim
    assert len(lead.evidence) >= 1
    assert lead.evidence[0].classification == "supports"

    # 2. Performed allowed restart action
    assert final_state.decision == "auto"
    assert len(final_state.actions_taken) == 1
    action = final_state.actions_taken[0]
    assert action["action"] == "restart_service"
    assert action["ok"] is True

    # 3. Verified recovery
    assert final_state.status == "resolved"


def test_scenario_slow_dependency_e2e(tmp_path):
    """Scenario 3: slow_dependency
    - identify dependency latency
    - investigate before acting
    - execute scale_service action
    - verify recovery
    """
    mem_file = str(tmp_path / "memory.sqlite")
    memory_store = IncidentMemoryStore(db_path=mem_file)

    final_state = run_scenario_e2e("slow_dependency", memory_store=memory_store)

    # 1. Identified dependency latency
    assert final_state.metadata["problem_area"] == "inventory-service"
    lead = final_state.hypotheses[0]
    assert "inventory service dependency high latency" in lead.claim.lower()
    assert len(lead.evidence) >= 1
    assert lead.evidence[0].classification == "supports"

    # 2. Performed allowed scale action
    assert final_state.decision in ("auto", "approve")
    assert len(final_state.actions_taken) == 1
    action = final_state.actions_taken[0]
    assert action["action"] == "scale_service"
    assert action["parameters"]["replicas"] == 3
    assert action["ok"] is True

    # 3. Verified recovery
    assert final_state.status == "resolved"


def test_scenario_false_alarm_e2e(tmp_path):
    """Scenario 4: false_alarm
    - recognize healthy system
    - skeptic challenges failure hypothesis
    - safety gate enforces NO ACTION
    """
    mem_file = str(tmp_path / "memory.sqlite")
    memory_store = IncidentMemoryStore(db_path=mem_file)

    final_state = run_scenario_e2e("false_alarm", memory_store=memory_store)

    # 1. Triage or skeptic recognized false alarm
    assert final_state.metadata.get("is_real_incident") is False or final_state.hypotheses[0].status == "falsified"

    # 2. Safety gate strictly enforces NO REMEDIATION ACTION
    assert final_state.decision == "escalate"
    assert len(final_state.actions_taken) == 0  # Zero actions taken


def test_scenario_ambiguous_e2e(tmp_path):
    """Scenario 5: ambiguous
    - maintain competing hypotheses with weak signals
    - confidence remains insufficient
    - ESCALATE safely instead of guessing
    """
    mem_file = str(tmp_path / "memory.sqlite")
    memory_store = IncidentMemoryStore(db_path=mem_file)

    # Gate threshold require > 0.60
    gate_cfg = GateConfig(auto_threshold=0.80, approve_threshold=0.60)
    final_state = run_scenario_e2e("ambiguous", gate_config=gate_cfg, memory_store=memory_store)

    # 1. Competing hypotheses maintained
    assert len(final_state.hypotheses) >= 2
    assert final_state.confidence < gate_cfg.approve_threshold

    # 2. Safety gate detects ambiguity/insufficient confidence and escalates
    assert final_state.decision == "escalate"
    assert len(final_state.actions_taken) == 0  # Zero blind actions taken
