"""Placeholder tests for remediation action tools."""

from falsify.tools.base import restart_service, rollback_deploy, scale_service, ToolResult


def test_restart_service_stub():
    """Verify restart_service returns a valid ToolResult."""
    res = restart_service("falsify-demo-payment")
    assert isinstance(res, ToolResult)
    assert res.tool == "restart_service"
    assert res.ok is True
    assert res.data["service"] == "falsify-demo-payment"
    assert res.data["action"] == "restart"


def test_rollback_deploy_stub():
    """Verify rollback_deploy returns a valid ToolResult."""
    res = rollback_deploy("falsify-demo-payment", "v1.0.0")
    assert isinstance(res, ToolResult)
    assert res.tool == "rollback_deploy"
    assert res.ok is True
    assert res.data["target_version"] == "v1.0.0"


def test_scale_service_stub():
    """Verify scale_service returns a valid ToolResult."""
    res = scale_service("falsify-demo-orders", 3)
    assert isinstance(res, ToolResult)
    assert res.tool == "scale_service"
    assert res.ok is True
    assert res.data["replicas"] == 3
