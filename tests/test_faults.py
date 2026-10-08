"""Tests for target fault injection framework and scenario alignments."""

import pytest
from pathlib import Path

from targets.faults import (
    FaultSpec,
    clear_active_fault,
    get_active_faults,
    inject_ambiguous,
    inject_bad_deploy,
    inject_db_pool_exhaustion,
    inject_false_alarm,
    inject_slow_dependency,
    reset_all_faults,
)


def test_faults_framework_placeholder():
    """Verify scenarios file exists and structure is ready for fault injection."""
    scenarios_path = Path(__file__).resolve().parent.parent / "docs" / "SCENARIOS.md"
    assert scenarios_path.exists()
    content = scenarios_path.read_text(encoding="utf-8")
    assert "scenario" in content.lower()


def test_fault_injection_and_cleanup():
    """Verify fault injection functions register and clear correctly."""
    reset_all_faults()
    assert len(get_active_faults()) == 0

    f1 = inject_bad_deploy()
    assert isinstance(f1, FaultSpec)
    assert f1.scenario_id == "bad_deploy"

    f2 = inject_db_pool_exhaustion()
    f3 = inject_slow_dependency()
    f4 = inject_false_alarm()
    f5 = inject_ambiguous()

    active = get_active_faults()
    assert len(active) == 5

    assert clear_active_fault("bad_deploy") is True
    assert len(get_active_faults()) == 4

    reset_all_faults()
    assert len(get_active_faults()) == 0
