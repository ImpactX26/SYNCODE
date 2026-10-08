"""Placeholder tests for diagnostic tools and safe_tool decorator."""

from falsify.tools.base import (
    ToolResult,
    get_db_stats,
    get_deploy_history,
    get_logs,
    get_metrics,
    probe_dependency,
    safe_tool,
)


def test_safe_tool_decorator_success():
    """Verify safe_tool decorator successfully wraps a function."""
    @safe_tool(tool_name="test_func")
    def sample_func(x: int):
        return {"result": x * 2}

    res = sample_func(5)
    assert isinstance(res, ToolResult)
    assert res.ok is True
    assert res.tool == "test_func"
    assert res.data == {"result": 10}
    assert res.error is None
    assert res.latency_ms >= 0


def test_safe_tool_decorator_exception():
    """Verify safe_tool catches exceptions and returns ok=False without crashing."""
    @safe_tool(tool_name="failing_func")
    def sample_fail():
        raise RuntimeError("Connection timed out")

    res = sample_fail()
    assert isinstance(res, ToolResult)
    assert res.ok is False
    assert res.tool == "failing_func"
    assert res.data is None
    assert "Connection timed out" in res.error
    assert res.latency_ms >= 0


def test_diagnostic_tool_stubs():
    """Verify all diagnostic tool stubs return valid ToolResults."""
    res_metrics = get_metrics("falsify-demo-gateway", "latency_p99")
    assert res_metrics.ok is True
    assert res_metrics.tool == "get_metrics"

    res_logs = get_logs("falsify-demo-gateway", lines=50)
    assert res_logs.ok is True
    assert res_logs.tool == "get_logs"

    res_deploy = get_deploy_history("falsify-demo-payment")
    assert res_deploy.ok is True
    assert res_deploy.tool == "get_deploy_history"

    res_probe = probe_dependency("http://localhost:8000/health")
    assert res_probe.ok is True
    assert res_probe.tool == "probe_dependency"

    res_db = get_db_stats("falsify-demo-db")
    assert res_db.ok is True
    assert res_db.tool == "get_db_stats"
