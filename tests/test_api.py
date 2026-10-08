"""Tests for FastAPI endpoints and server in app/main.py."""

import json
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


def test_get_nonexistent_incident(client):
    """Verify 404 on invalid/missing incident ID."""
    resp = client.get("/incidents/nonexistent_inc_99999")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_run_scenario_api(client):
    """Verify scenario execution endpoint."""
    resp = client.post("/scenarios/bad_deploy/run")
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["scenario"] == "bad_deploy"
    assert res_data["status"] == "resolved"
    assert res_data["decision"] == "auto"
    assert len(res_data["actions_taken"]) == 1


def test_run_invalid_scenario_api(client):
    """Verify 404 on unknown scenario key."""
    resp = client.post("/scenarios/unknown_scenario_xyz/run")
    assert resp.status_code == 404


def test_websocket_event_stream(client):
    """Verify WebSocket connection and real-time event broadcasting."""
    with client.websocket_connect("/ws/events") as websocket:
        # Trigger an incident creation in parallel to verify event broadcast
        req = {
            "title": "WebSocket Realtime Alert",
            "description": "Triggered for WS stream test",
            "metadata": {"service": "falsify-demo-payment"},
        }
        resp = client.post("/incidents", json=req)
        assert resp.status_code == 200

        # Receive broadcasted event over WebSocket
        msg_text = websocket.receive_text()
        event = json.loads(msg_text)
        assert event["type"] == "incident_opened"
        assert event["payload"]["title"] == "WebSocket Realtime Alert"
