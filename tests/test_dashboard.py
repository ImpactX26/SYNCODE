"""Tests for Phase D4 Demo Presentation Dashboard and Scenario Fixtures."""

import json
from pathlib import Path
import pytest


def test_dashboard_files_exist():
    """Verify all dashboard UI assets exist."""
    dashboard_dir = Path(__file__).resolve().parent.parent / "app" / "dashboard"
    assert (dashboard_dir / "index.html").is_file()
    assert (dashboard_dir / "style.css").is_file()
    assert (dashboard_dir / "app.js").is_file()
    assert (dashboard_dir / "mock_data.js").is_file()


def test_index_html_contains_required_elements():
    """Verify index.html contains all 5 scenarios and essential UI components."""
    html_file = Path(__file__).resolve().parent.parent / "app" / "dashboard" / "index.html"
    content = html_file.read_text(encoding="utf-8")

    # Verify 5 scenarios in dropdown
    assert 'value="bad_deploy"' in content
    assert 'value="db_pool_exhaustion"' in content
    assert 'value="slow_dependency"' in content
    assert 'value="false_alarm"' in content
    assert 'value="ambiguous"' in content

    # Verify 8-step pipeline
    assert "Observe" in content
    assert "Hypothesize" in content
    assert "Experiment" in content
    assert "Skeptic" in content
    assert "Safety Gate" in content
    assert "Act" in content
    assert "Verify" in content
    assert "Outcome" in content

    # Verify key sections
    assert "scenario-select" in content
    assert "btn-play" in content
    assert "btn-step" in content
    assert "btn-reset" in content
    assert "confidence-bar-fill" in content
    assert "hypotheses-list" in content
    assert "skeptic-card" in content
    assert "gate-status-pill" in content
    assert "action-card" in content
    assert "verification-card" in content
    assert "events-container" in content


def test_mock_data_scenarios():
    """Verify mock_data.js contains all 5 scenarios with event timelines."""
    mock_file = Path(__file__).resolve().parent.parent / "app" / "dashboard" / "mock_data.js"
    content = mock_file.read_text(encoding="utf-8")

    for scenario_name in [
        "bad_deploy",
        "db_pool_exhaustion",
        "slow_dependency",
        "false_alarm",
        "ambiguous",
    ]:
        assert scenario_name in content

    # Verify event types are used
    for event_type in [
        "incident_opened",
        "hypotheses_proposed",
        "tool_called",
        "hypothesis_updated",
        "skeptic_note",
        "decision_made",
        "action_taken",
        "recovery_checked",
        "incident_closed",
    ]:
        assert event_type in content


def test_app_js_websocket_and_controller():
    """Verify app.js includes WebSocket support and simulation controller."""
    js_file = Path(__file__).resolve().parent.parent / "app" / "dashboard" / "app.js"
    content = js_file.read_text(encoding="utf-8")

    assert "DashboardController" in content
    assert "loadScenario" in content
    assert "runBackendScenario" in content
    assert "togglePlay" in content
    assert "stepForward" in content
    assert "resetScenario" in content
    assert "connectWebSocket" in content
    assert "ws://localhost:8000/ws/events" in content


def test_dashboard_http_endpoints_return_200():
    """Verify all dashboard routes and static assets return HTTP 200."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    routes = [
        "/",
        "/dashboard",
        "/style.css",
        "/mock_data.js",
        "/app.js",
        "/static/style.css",
        "/static/mock_data.js",
        "/static/app.js",
        "/static/index.html",
    ]

    for route in routes:
        resp = client.get(route)
        assert resp.status_code == 200, f"Route '{route}' failed with status {resp.status_code}"

