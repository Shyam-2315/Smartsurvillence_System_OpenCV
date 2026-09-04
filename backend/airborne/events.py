from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

import config
from .models import MISSION_EVENT_TYPES


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.settings.database_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _serialize(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["metadata"] = json.loads(result.pop("metadata_json") or "{}")
    return result


def create(mission_id: str, event_type: str, *, severity: str = "info", camera_id: str | None = None,
           incident_id: int | None = None, evidence_id: str | None = None, analysis_id: str | None = None,
           metadata: dict[str, Any] | None = None, timestamp: str | None = None) -> dict[str, Any]:
    if event_type not in MISSION_EVENT_TYPES:
        raise ValueError(f"Unsupported mission event type: {event_type}")
    event_id, timestamp = str(uuid.uuid4()), timestamp or datetime.now(timezone.utc).isoformat()
    conn = _conn()
    try:
        conn.execute("""INSERT INTO mission_events
            (id,mission_id,timestamp,event_type,severity,camera_id,incident_id,evidence_id,analysis_id,metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (event_id, mission_id, timestamp, event_type, severity, camera_id, incident_id, evidence_id, analysis_id, json.dumps(metadata or {})))
        conn.commit()
        row = conn.execute("SELECT * FROM mission_events WHERE id=?", (event_id,)).fetchone()
    finally:
        conn.close()
    return _serialize(row)


def list_for_mission(mission_id: str) -> list[dict[str, Any]]:
    conn = _conn()
    try:
        rows = conn.execute("SELECT * FROM mission_events WHERE mission_id=? ORDER BY timestamp DESC, id DESC", (mission_id,)).fetchall()
    finally:
        conn.close()
    return [_serialize(row) for row in rows]

