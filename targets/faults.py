"""Target fault injection and simulation module for Falsify demo scenarios."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FaultSpec(BaseModel):
    """Specification of an injected fault in the target demo environment."""
    scenario_id: str
    name: str
    target_service: str
    blast_radius: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    injected_at: float = Field(default_factory=time.time)
    active: bool = True


# In-memory registry of active faults
_ACTIVE_FAULTS: Dict[str, FaultSpec] = {}


def inject_bad_deploy(
    service_name: str = "falsify-demo-payment",
    version: str = "v1.2.4",
) -> FaultSpec:
    """Inject a bad deployment fault (regression introducing NullPointerException)."""
    spec = FaultSpec(
        scenario_id="bad_deploy",
        name="Faulty Deployment v1.2.4",
        target_service=service_name,
        blast_radius="low",
        description="Regression in v1.2.4 introducing NullPointerException on checkout payload",
        parameters={"version": version, "error_type": "NullPointerException", "error_rate": 0.15},
    )
    _ACTIVE_FAULTS["bad_deploy"] = spec
    return spec


def inject_db_pool_exhaustion(
    service_name: str = "falsify-demo-payment",
    db_target: str = "falsify-demo-db",
) -> FaultSpec:
    """Inject database connection pool exhaustion fault."""
    spec = FaultSpec(
        scenario_id="db_pool_exhaustion",
        name="Database Connection Pool Exhaustion",
        target_service=service_name,
        blast_radius="medium",
        description="Database connection handles saturated at 100/100 with waiting queues",
        parameters={"db_target": db_target, "active_connections": 100, "max_connections": 100},
    )
    _ACTIVE_FAULTS["db_pool_exhaustion"] = spec
    return spec


def inject_slow_dependency(
    service_name: str = "falsify-demo-inventory",
    latency_ms: int = 2100,
) -> FaultSpec:
    """Inject downstream dependency latency bottleneck."""
    spec = FaultSpec(
        scenario_id="slow_dependency",
        name="Downstream Inventory Service Latency",
        target_service=service_name,
        blast_radius="medium",
        description=f"Downstream service response latency degraded to {latency_ms}ms",
        parameters={"latency_ms": latency_ms, "target_url": "http://inventory-service:8080/health"},
    )
    _ACTIVE_FAULTS["slow_dependency"] = spec
    return spec


def inject_false_alarm(
    service_name: str = "falsify-demo-gateway",
) -> FaultSpec:
    """Inject a transient monitoring alert artifact with healthy target containers."""
    spec = FaultSpec(
        scenario_id="false_alarm",
        name="Transient Synthetic Scraper Spike",
        target_service=service_name,
        blast_radius="low",
        description="Transient metric spike artifact; all services remain 100% healthy",
        parameters={"metric_spike": 0.12, "actual_error_rate": 0.0001},
    )
    _ACTIVE_FAULTS["false_alarm"] = spec
    return spec


def inject_ambiguous(
    service_name: str = "falsify-demo-gateway",
) -> FaultSpec:
    """Inject weak multi-point network/DNS jitter producing ambiguous diagnosis."""
    spec = FaultSpec(
        scenario_id="ambiguous",
        name="Intermittent Distributed Network & DNS Jitter",
        target_service=service_name,
        blast_radius="high",
        description="Intermittent socket timeouts and DNS warnings across multiple components",
        parameters={"symptoms": ["dns_timeout", "socket_drop", "db_read_timeout"]},
    )
    _ACTIVE_FAULTS["ambiguous"] = spec
    return spec


def get_active_faults() -> List[FaultSpec]:
    """Retrieve all currently active faults."""
    return list(_ACTIVE_FAULTS.values())


def clear_active_fault(scenario_id: str) -> bool:
    """Clear an active fault by scenario ID."""
    if scenario_id in _ACTIVE_FAULTS:
        del _ACTIVE_FAULTS[scenario_id]
        return True
    return False


def reset_all_faults() -> None:
    """Clear all active faults in the environment."""
    _ACTIVE_FAULTS.clear()
