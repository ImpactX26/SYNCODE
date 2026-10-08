import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from falsify.confidence import get_leading_hypothesis
from falsify.state import IncidentState


class IncidentMemoryRecord(BaseModel):
    """Persisted record of a resolved incident."""

    incident_id: str
    title: str
    root_cause_claim: str
    remediation_action: str
    verified: bool
    state_snapshot: Dict[str, Any]
    recorded_at: float


class IncidentMemoryStore:
    """Storage interface for remembering past incidents in SQLite."""

    def __init__(self, db_path: str = "eval/incident_memory.sqlite"):
        self.db_path = db_path
        self._memory_conn: Optional[sqlite3.Connection] = None
        if db_path == ":memory:":
            self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._memory_conn.row_factory = sqlite3.Row
        else:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._memory_conn is not None:
            return self._memory_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._get_connection()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS incident_memory (
                incident_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                root_cause_claim TEXT,
                remediation_action TEXT,
                verified INTEGER NOT NULL,
                state_snapshot TEXT NOT NULL,
                recorded_at REAL NOT NULL
            )
            """
        )
        conn.commit()
        if self._memory_conn is None:
            conn.close()

    def save_incident(self, state: IncidentState) -> bool:
        """Store incident record in SQLite store."""
        lead = get_leading_hypothesis(state.hypotheses)
        root_cause = lead.claim if lead else ""
        action = state.actions_taken[-1]["action"] if state.actions_taken else ""
        verified = 1 if state.status == "resolved" else 0
        snapshot = json.dumps(state.model_dump())

        conn = self._get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO incident_memory 
            (incident_id, title, root_cause_claim, remediation_action, verified, state_snapshot, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (state.incident_id, state.title, root_cause, action, verified, snapshot, time.time()),
        )
        conn.commit()
        if self._memory_conn is None:
            conn.close()
        return True

    def find_similar_incidents(self, title: str, limit: int = 3) -> List[IncidentMemoryRecord]:
        """Query past incidents for similar symptoms or root causes."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM incident_memory ORDER BY recorded_at DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        results = []
        for row in rows:
            results.append(
                IncidentMemoryRecord(
                    incident_id=row["incident_id"],
                    title=row["title"],
                    root_cause_claim=row["root_cause_claim"] or "",
                    remediation_action=row["remediation_action"] or "",
                    verified=bool(row["verified"]),
                    state_snapshot=json.loads(row["state_snapshot"]),
                    recorded_at=row["recorded_at"],
                )
            )
        if self._memory_conn is None:
            conn.close()
        return results
