"""Placeholder tests for overall budget limits (LLM calls, tool calls, elapsed time)."""

from falsify.budget import BudgetConfig, BudgetTracker


def test_budget_call_limits():
    """Verify tool call and LLM call budget limits."""
    config = BudgetConfig(max_llm_calls=2, max_tool_calls=3)
    tracker = BudgetTracker(config=config)

    tracker.record_llm_call()
    assert not tracker.is_exceeded()
    tracker.record_llm_call()
    assert tracker.is_exceeded()

    tracker_tools = BudgetTracker(config=config)
    tracker_tools.record_tool_call()
    tracker_tools.record_tool_call()
    assert not tracker_tools.is_exceeded()
    tracker_tools.record_tool_call()
    assert tracker_tools.is_exceeded()
