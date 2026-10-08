"""Falsify tool interface and base utilities."""

from __future__ import annotations

import functools
import time
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """Standard result structure returned by all Falsify diagnostic and remediation tools."""

    tool: str = Field(..., description="Name of the tool executed")
    ok: bool = Field(..., description="Whether the tool execution succeeded")
    data: Any = Field(default=None, description="Output payload or telemetry data (untrusted)")
    error: Optional[str] = Field(default=None, description="Error message if execution failed")
    latency_ms: float = Field(default=0.0, description="Execution duration in milliseconds")
    source: str = Field(default="mock", description="Source provider or target system name")


def safe_tool(tool_name: Optional[str] = None, default_source: str = "stub"):
    """Decorator to catch exceptions, enforce timeout/safety, track latency, and return a ToolResult."""

    def decorator(func: Callable[..., Any]) -> Callable[..., ToolResult]:
        name = tool_name or func.__name__

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> ToolResult:
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                if isinstance(result, ToolResult):
                    if not result.latency_ms:
                        result.latency_ms = latency_ms
                    return result
                return ToolResult(
                    tool=name,
                    ok=True,
                    data=result,
                    error=None,
                    latency_ms=latency_ms,
                    source=default_source,
                )
            except Exception as e:
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                return ToolResult(
                    tool=name,
                    ok=False,
                    data=None,
                    error=str(e),
                    latency_ms=latency_ms,
                    source=default_source,
                )

        return wrapper

    return decorator


# =====================================================================
# Typed Placeholder Diagnostic Tools (Stubs)
# =====================================================================

@safe_tool(tool_name="get_metrics", default_source="metrics_stub")
def get_metrics(service_name: str, metric_name: str, duration_mins: int = 15) -> ToolResult:
    """Retrieve time-series metrics for a given service.
    
    Args:
        service_name: Name of the target service or container.
        metric_name: Name of metric (e.g., 'cpu_percent', 'error_rate', 'latency_p99').
        duration_mins: Time window in minutes.
    """
    return ToolResult(
        tool="get_metrics",
        ok=True,
        data={"service": service_name, "metric": metric_name, "points": []},
        error=None,
        latency_ms=1.0,
        source="metrics_stub",
    )


@safe_tool(tool_name="get_logs", default_source="logs_stub")
def get_logs(service_name: str, lines: int = 100, pattern: Optional[str] = None) -> ToolResult:
    """Retrieve recent log lines for a given service with optional pattern filter.
    
    Args:
        service_name: Target service or container name.
        lines: Maximum number of log lines to return.
        pattern: Optional regex or substring filter.
    """
    return ToolResult(
        tool="get_logs",
        ok=True,
        data={"service": service_name, "lines": [], "pattern": pattern},
        error=None,
        latency_ms=1.0,
        source="logs_stub",
    )


@safe_tool(tool_name="get_deploy_history", default_source="deploy_stub")
def get_deploy_history(service_name: str, limit: int = 5) -> ToolResult:
    """Retrieve deployment history and recent releases for a service.
    
    Args:
        service_name: Target service name.
        limit: Number of recent deployments to fetch.
    """
    return ToolResult(
        tool="get_deploy_history",
        ok=True,
        data={"service": service_name, "deployments": []},
        error=None,
        latency_ms=1.0,
        source="deploy_stub",
    )


@safe_tool(tool_name="probe_dependency", default_source="network_stub")
def probe_dependency(target_url: str, timeout_sec: float = 2.0) -> ToolResult:
    """Check connectivity, response latency, and HTTP status of a dependency.
    
    Args:
        target_url: Target URL or endpoint to probe.
        timeout_sec: Timeout for probe in seconds.
    """
    return ToolResult(
        tool="probe_dependency",
        ok=True,
        data={"target_url": target_url, "status_code": 200, "reachable": True},
        error=None,
        latency_ms=1.0,
        source="network_stub",
    )


@safe_tool(tool_name="get_db_stats", default_source="db_stub")
def get_db_stats(db_identifier: str) -> ToolResult:
    """Retrieve connection pool, active queries, and health stats for a database.
    
    Args:
        db_identifier: Database container or connection alias.
    """
    return ToolResult(
        tool="get_db_stats",
        ok=True,
        data={"db_identifier": db_identifier, "active_connections": 0, "max_connections": 100},
        error=None,
        latency_ms=1.0,
        source="db_stub",
    )


# =====================================================================
# Typed Placeholder Remediation Tools (Stubs)
# =====================================================================

@safe_tool(tool_name="restart_service", default_source="action_stub")
def restart_service(service_name: str) -> ToolResult:
    """Restart a demo service container.
    
    Args:
        service_name: Name of the demo container to restart.
    """
    return ToolResult(
        tool="restart_service",
        ok=True,
        data={"service": service_name, "action": "restart", "status": "simulated_success"},
        error=None,
        latency_ms=1.0,
        source="action_stub",
    )


@safe_tool(tool_name="rollback_deploy", default_source="action_stub")
def rollback_deploy(service_name: str, target_version: Optional[str] = None) -> ToolResult:
    """Roll back a service to its previous stable release or specified version tag.
    
    Args:
        service_name: Name of the demo service.
        target_version: Optional target version hash or tag.
    """
    return ToolResult(
        tool="rollback_deploy",
        ok=True,
        data={"service": service_name, "action": "rollback", "target_version": target_version or "previous"},
        error=None,
        latency_ms=1.0,
        source="action_stub",
    )


@safe_tool(tool_name="scale_service", default_source="action_stub")
def scale_service(service_name: str, replicas: int) -> ToolResult:
    """Scale the replica count for a demo service.
    
    Args:
        service_name: Name of the demo service.
        replicas: Desired number of container instances.
    """
    return ToolResult(
        tool="scale_service",
        ok=True,
        data={"service": service_name, "action": "scale", "replicas": replicas},
        error=None,
        latency_ms=1.0,
        source="action_stub",
    )
