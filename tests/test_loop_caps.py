"""Placeholder tests for investigation/recovery loop iteration caps."""

from falsify.budget import BudgetConfig, BudgetTracker


def test_budget_loop_caps():
    """Verify loop iterations are capped at maximum configured limit (default 3)."""
    config = BudgetConfig(max_iterations=3)
    tracker = BudgetTracker(config=config)

    assert tracker.iterations == 0
    assert not tracker.is_exceeded()

    tracker.record_iteration()
    tracker.record_iteration()
    assert not tracker.is_exceeded()

    tracker.record_iteration()
    assert tracker.iterations == 3
    assert tracker.is_exceeded()
