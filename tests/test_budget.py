"""Comprehensive tests for execution budget, tool limits, and safe escalation."""

import time
import pytest
from falsify.budget import BudgetConfig, BudgetTracker
from falsify.state import IncidentState


def test_budget_call_limits():
    """Verify tool call and LLM call budget limits."""
    config = BudgetConfig(max_llm_calls=2, max_tool_calls=3)
    tracker = BudgetTracker(config=config)

    tracker.record_llm_call()
    assert not tracker.is_exceeded()
    tracker.record_llm_call()
    assert tracker.is_exceeded()
    assert "LLM call budget exhausted" in tracker.get_exhaustion_reason()

    tracker_tools = BudgetTracker(config=config)
    tracker_tools.record_tool_call()
    tracker_tools.record_tool_call()
    assert not tracker_tools.is_exceeded()
    tracker_tools.record_tool_call()
    assert tracker_tools.is_exceeded()
    assert "Tool call budget exhausted" in tracker_tools.get_exhaustion_reason()


def test_budget_iteration_limits():
    """Verify iteration limits prevent infinite loop execution."""
    config = BudgetConfig(max_iterations=3)
    tracker = BudgetTracker(config=config)

    for i in range(2):
        tracker.record_iteration()
        assert not tracker.is_exceeded()

    tracker.record_iteration()
    assert tracker.iterations == 3
    assert tracker.is_exceeded()
    assert "Maximum loop iterations reached" in tracker.get_exhaustion_reason()


def test_check_and_enforce_budget_escalates_state():
    """Verify check_and_enforce_budget sets decision to escalate and records error."""
    config = BudgetConfig(max_tool_calls=1)
    tracker = BudgetTracker(config=config)
    tracker.record_tool_call()

    state = IncidentState(title="Test budget exhaustion")
    exceeded, reason = tracker.check_and_enforce_budget(state)

    assert exceeded is True
    assert state.decision == "escalate"
    assert any("Budget exceeded" in err for err in state.errors)


def test_elapsed_time_budget_exhaustion():
    """Verify elapsed time budget limit detection."""
    config = BudgetConfig(max_elapsed_sec=0.01)
    tracker = BudgetTracker(config=config)
    time.sleep(0.02)

    assert tracker.is_exceeded()
    assert "Elapsed time budget exhausted" in tracker.get_exhaustion_reason()
