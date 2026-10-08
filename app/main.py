"""FastAPI application server for Falsify API, WebSocket event stream, and Live Dashboard."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from falsify.memory import IncidentMemoryStore
from falsify.scenarios import (
    SCENARIO_INITIAL_STATES,
    get_scenario_initial_state,
    run_scenario_e2e,
)
from falsify.state import IncidentState

app = FastAPI(
    title="Falsify Incident Remediation System",
    description="Agentic SRE Incident Investigation & Automated Remediation API",
    version="1.0.0",
)

# Enable CORS for local dev / frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for active incidents and active WebSocket clients
_INCIDENT_STORE: Dict[str, IncidentState] = {}
_ACTIVE_WEBSOCKETS: List[WebSocket] = []
_MEMORY_STORE = IncidentMemoryStore(os.getenv("INCIDENT_MEMORY_DB", "eval/incident_memory.sqlite"))


class CreateIncidentRequest(BaseModel):
    title: str = Field(..., description="Incident alert title")
    description: Optional[str] = Field(default="", description="Optional description")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata and context")


class CreateIncidentResponse(BaseModel):
    incident_id: str
    status: str
    message: str


# =====================================================================
# REST Endpoints
# =====================================================================

@app.get("/healthz")
def healthz() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "falsify-api"}


@app.get("/scenarios")
def list_scenarios() -> Dict[str, Any]:
    """List all supported incident scenarios."""
    scenarios_meta = {
        "bad_deploy": {
            "name": "Bad Deployment (v1.2.4 Regression)",
            "service": "falsify-demo-payment",
            "expected_outcome": "Rollback to v1.2.3 and verify error rate recovers",
        },
        "db_pool_exhaustion": {
            "name": "Database Pool Saturation",
            "service": "falsify-demo-payment / db",
            "expected_outcome": "Restart service container and verify connection pool drops",
        },
        "slow_dependency": {
            "name": "Downstream Dependency Latency",
            "service": "falsify-demo-inventory",
            "expected_outcome": "Scale inventory replica count to 3 and verify latency normalizes",
        },
        "false_alarm": {
            "name": "False Alarm Metric Spike",
            "service": "falsify-demo-gateway",
            "expected_outcome": "Skeptic challenges alert; Safety Gate strictly blocks action",
        },
        "ambiguous": {
            "name": "Ambiguous Distributed Failure",
            "service": "Distributed Mesh",
            "expected_outcome": "Inconclusive telemetry; Escalates safely to human SRE without blind action",
        },
    }
    return {"scenarios": scenarios_meta}


@app.post("/incidents", response_model=CreateIncidentResponse)
async def create_incident(req: CreateIncidentRequest) -> CreateIncidentResponse:
    """Ingest or trigger a new incident investigation."""
    state = IncidentState(
        title=req.title,
        metadata=req.metadata,
        status="investigating",
    )
    _INCIDENT_STORE[state.incident_id] = state

    # Broadcast incident opened event
    await broadcast_event({
        "ts": state.metadata.get("timestamp", 0) or 0.0,
        "incident_id": state.incident_id,
        "type": "incident_opened",
        "payload": {
            "title": state.title,
            "description": req.description,
        },
    })

    return CreateIncidentResponse(
        incident_id=state.incident_id,
        status="investigating",
        message="Incident created and investigation started.",
    )


@app.get("/incidents/{incident_id}")
def get_incident(incident_id: str) -> Dict[str, Any]:
    """Retrieve full IncidentState snapshot."""
    if incident_id not in _INCIDENT_STORE:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found.")
    return _INCIDENT_STORE[incident_id].model_dump()


@app.post("/scenarios/{scenario_key}/run")
async def run_scenario(scenario_key: str) -> Dict[str, Any]:
    """Execute a scenario end-to-end and broadcast events over WebSocket."""
    if scenario_key not in SCENARIO_INITIAL_STATES:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_key}' not found.")

    final_state = run_scenario_e2e(scenario_key, memory_store=_MEMORY_STORE)
    _INCIDENT_STORE[final_state.incident_id] = final_state

    # Stream all recorded events to connected WebSocket clients
    for ev in final_state.events:
        await broadcast_event(ev)
        await asyncio.sleep(0.05)

    return {
        "scenario": scenario_key,
        "incident_id": final_state.incident_id,
        "decision": final_state.decision,
        "confidence": final_state.confidence,
        "status": final_state.status,
        "actions_taken": final_state.actions_taken,
    }


# =====================================================================
# WebSocket Event Stream
# =====================================================================

async def broadcast_event(event_envelope: Dict[str, Any]) -> None:
    """Send JSON event envelope to all connected WebSockets."""
    text_data = json.dumps(event_envelope)
    for ws in list(_ACTIVE_WEBSOCKETS):
        try:
            await ws.send_text(text_data)
        except Exception:
            if ws in _ACTIVE_WEBSOCKETS:
                _ACTIVE_WEBSOCKETS.remove(ws)


@app.websocket("/ws/events")
async def websocket_event_stream(websocket: WebSocket) -> None:
    """Real-time event stream for the live presentation dashboard."""
    await websocket.accept()
    _ACTIVE_WEBSOCKETS.append(websocket)
    try:
        while True:
            # Keepalive listener
            data = await websocket.receive_text()
            # If client sends a run command, handle it
            try:
                msg = json.loads(data)
                if msg.get("action") == "run_scenario" and msg.get("scenario"):
                    await run_scenario(msg["scenario"])
            except Exception:
                pass
    except WebSocketDisconnect:
        if websocket in _ACTIVE_WEBSOCKETS:
            _ACTIVE_WEBSOCKETS.remove(websocket)


# =====================================================================
# Static Dashboard Mounting
# =====================================================================

DASHBOARD_DIR = Path(__file__).resolve().parent / "dashboard"

if DASHBOARD_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(DASHBOARD_DIR)), name="static")

    @app.get("/")
    def serve_dashboard_root() -> FileResponse:
        return FileResponse(str(DASHBOARD_DIR / "index.html"))

    @app.get("/dashboard")
    def serve_dashboard() -> FileResponse:
        return FileResponse(str(DASHBOARD_DIR / "index.html"))

    @app.get("/style.css")
    def serve_style_css() -> FileResponse:
        return FileResponse(str(DASHBOARD_DIR / "style.css"), media_type="text/css")

    @app.get("/mock_data.js")
    def serve_mock_data_js() -> FileResponse:
        return FileResponse(str(DASHBOARD_DIR / "mock_data.js"), media_type="application/javascript")

    @app.get("/app.js")
    def serve_app_js() -> FileResponse:
        return FileResponse(str(DASHBOARD_DIR / "app.js"), media_type="application/javascript")
