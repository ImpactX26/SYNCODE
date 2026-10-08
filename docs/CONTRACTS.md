# Falsify System Contracts & Interface Specifications

This document defines the shared data schemas, tool signatures, event interfaces, and API endpoints for the Falsify Agentic AI SRE Incident Investigation System. All development across Phases A1–A5 must adhere strictly to these contracts.

---

## 1. ToolResult Schema

Every diagnostic or remediation tool executed by the agent must catch all exceptions and return a `ToolResult` instance. Tools must never raise unhandled exceptions or crash the workflow.

```python
class ToolResult(BaseModel):
    tool: str             # Identifier of the executed tool
    ok: bool              # True if execution succeeded, False on error/timeout
    data: Any = None      # Returned telemetry/payload (treated as UNTRUSTED DATA)
    error: Optional[str]  # Error message or reason on failure
    latency_ms: float     # Execution elapsed time in milliseconds
    source: str = "mock"  # Provider or system origin (e.g. docker, prometheus, stub)
```

JSON representation:
```json
{
  "tool": "get_metrics",
  "ok": true,
  "data": {
    "service": "payment-service",
    "metric": "error_rate",
    "points": []
  },
  "error": null,
  "latency_ms": 14.2,
  "source": "metrics_stub"
}
```

---

## 2. IncidentState Schema

The shared graph state across the entire LangGraph workflow.

```python
EvidenceClassification = Literal["supports", "contradicts", "inconclusive"]
HypothesisStatus = Literal["alive", "falsified", "uncertain"]
DecisionStatus = Literal["auto", "approve", "escalate", "pending"]

class Evidence(BaseModel):
    id: str
    source: str
    claim: str
    finding: str
    classification: EvidenceClassification
    timestamp: float
    data: Dict[str, Any]

class Hypothesis(BaseModel):
    id: str
    claim: str
    prediction: str
    status: HypothesisStatus
    evidence: List[Evidence]
    created_at: float

class IncidentState(BaseModel):
    incident_id: str
    title: str
    status: str
    blast_radius: str
    hypotheses: List[Hypothesis]
    confidence: float
    decision: DecisionStatus
    iterations: int
    actions_taken: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    events: List[Dict[str, Any]]
    errors: List[str]
```

JSON representation:
```json
{
  "incident_id": "inc_1728390000",
  "title": "High HTTP 500 error spike on /checkout",
  "status": "investigating",
  "blast_radius": "medium",
  "hypotheses": [
    {
      "id": "hyp_01",
      "claim": "Database connection pool exhaustion in payment-db",
      "prediction": "Active connections equal max_connections in db stats",
      "status": "alive",
      "evidence": [
        {
          "id": "ev_01",
          "source": "get_db_stats",
          "claim": "Database connection pool exhaustion in payment-db",
          "finding": "active_connections: 100, max_connections: 100",
          "classification": "supports",
          "timestamp": 1728390050.0,
          "data": { "active_connections": 100, "max_connections": 100 }
        }
      ],
      "created_at": 1728390010.0
    }
  ],
  "confidence": 0.60,
  "decision": "pending",
  "iterations": 1,
  "actions_taken": [],
  "metadata": {},
  "events": [],
  "errors": []
}
```

---

## 3. Placeholder Tool Signatures

All tools are located in `falsify/tools/base.py` and decorated with `@safe_tool`.

### Diagnostic Tools

```python
def get_metrics(
    service_name: str,
    metric_name: str,
    duration_mins: int = 15
) -> ToolResult:
    """Retrieve time-series metrics for a given service."""

def get_logs(
    service_name: str,
    lines: int = 100,
    pattern: Optional[str] = None
) -> ToolResult:
    """Retrieve recent log lines for a service with optional regex/text filter."""

def get_deploy_history(
    service_name: str,
    limit: int = 5
) -> ToolResult:
    """Retrieve recent deployment history and release tags."""

def probe_dependency(
    target_url: str,
    timeout_sec: float = 2.0
) -> ToolResult:
    """Probe network connectivity, HTTP response code, and latency to dependency."""

def get_db_stats(
    db_identifier: str
) -> ToolResult:
    """Retrieve database connection pool metrics, lock stats, and health."""
```

### Remediation Tools (Allow-listed)

```python
def restart_service(
    service_name: str
) -> ToolResult:
    """Restart a demo service container."""

def rollback_deploy(
    service_name: str,
    target_version: Optional[str] = None
) -> ToolResult:
    """Roll back service to previous release or target version."""

def scale_service(
    service_name: str,
    replicas: int
) -> ToolResult:
    """Scale replica count for a demo service."""
```

---

## 4. Dashboard Event Schema

All events streamed over WebSockets or logged to the audit trail follow this exact envelope:

```json
{
  "ts": 1728390000.123,
  "incident_id": "inc_1728390000",
  "type": "<EVENT_TYPE>",
  "payload": { ... }
}
```

### Allowed Event Types

| Event Type | Emitted By | Payload Description |
| :--- | :--- | :--- |
| `incident_opened` | Monitor / Ingestion | Trigger alert details, title, timestamp |
| `hypotheses_proposed` | Hypothesis Node | List of generated competing hypotheses |
| `tool_called` | Experiment / Action Node | Tool name, parameters, result summary |
| `hypothesis_updated` | Experiment Node | Hypothesis ID, updated status, attached evidence |
| `skeptic_note` | Skeptic Node | Counter-arguments, flaws, critique |
| `decision_made` | Decision Gate | Decision outcome (`auto`, `approve`, `escalate`), confidence |
| `action_taken` | Action Node | Allow-listed action executed, target container |
| `recovery_checked` | Verification Node | Verification probe result, recovery status |
| `incident_closed` | Workflow End | Final resolution summary, total time, status |
| `memory_saved` | Memory Node | SQLite snapshot record metadata |

---

## 5. Planned API Endpoints

```
POST /incidents
  Summary: Trigger or ingest a new incident
  Request Body: { "title": str, "description": str, "metadata": dict }
  Response: { "incident_id": str, "status": "investigating" }

GET /incidents/{id}
  Summary: Retrieve full IncidentState snapshot
  Response: IncidentState schema

WebSocket /ws/events
  Summary: Real-time event stream for the live dashboard
  Protocol: JSON WebSocket stream emitting Dashboard Event envelopes
```
