"""Tests for FastAPI endpoints and server in app/main.py."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_healthz(client):
    """Verify healthz endpoint."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_list_scenarios(client):
    """Verify scenario listing endpoint."""
    resp = client.get("/scenarios")
    assert resp.status_code == 200
    scenarios = resp.json()["scenarios"]
    assert "bad_deploy" in scenarios
    assert "db_pool_exhaustion" in scenarios
    assert "slow_dependency" in scenarios
    assert "false_alarm" in scenarios
    assert "ambiguous" in scenarios


def test_create_and_get_incident(client):
    """Verify incident creation and retrieval."""
    req = {
        "title": "High error rate on gateway",
        "description": "Spike in HTTP 500s",
        "metadata": {"service": "falsify-demo-gateway"},
    }
    resp = client.post("/incidents", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert "incident_id" in data
    inc_id = data["incident_id"]

    get_resp = client.get(f"/incidents/{inc_id}")
    assert get_resp.status_code == 200
    state = get_resp.json()
    assert state["title"] == "High error rate on gateway"
    assert state["status"] == "investigating"


def test_run_scenario_api(client):
    """Verify scenario execution endpoint."""
    resp = client.post("/scenarios/bad_deploy/run")
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["scenario"] == "bad_deploy"
    assert res_data["status"] == "resolved"
    assert res_data["decision"] == "auto"
    assert len(res_data["actions_taken"]) == 1
