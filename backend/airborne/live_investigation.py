"""Explicit local Visual Intelligence hand-off for live airborne evidence."""
from __future__ import annotations

import json
import sqlite3
from fastapi import HTTPException

import config
from . import evidence

def investigate(evidence_id: str) -> dict:
    conn = sqlite3.connect(config.settings.database_path, timeout=10); conn.row_factory = sqlite3.Row
    try: row = conn.execute("SELECT * FROM mission_evidence WHERE id=? AND source_type='airborne_live_capture'", (evidence_id,)).fetchone()
    finally: conn.close()
    if not row: raise HTTPException(404, "Airborne live evidence not found")
    item = dict(row); mission_id = item["mission_id"]
    from visual_intelligence import service as visual_service
    if item["analysis_id"]: return visual_service.get(item["analysis_id"])
    event_id = None
    if mission_id:
        conn = sqlite3.connect(config.settings.database_path); row_event = conn.execute("SELECT id FROM mission_events WHERE mission_id=? AND evidence_id=? ORDER BY timestamp DESC LIMIT 1", (mission_id, evidence_id)).fetchone(); conn.close()
        event_id = row_event[0] if row_event else None
    metadata = json.loads(item["metadata_json"] or "{}")
    path = evidence.original_path(evidence_id)
    created = visual_service.create_bytes(path.read_bytes(), "airborne-live-evidence.jpg", source_type="airborne_live_capture",
        source_metadata={"mission_id": mission_id, "mission_event_id": event_id, "evidence_id": evidence_id, "telemetry": metadata.get("telemetry"), "telemetry_timestamp": metadata.get("telemetry_timestamp"), "delta_ms": metadata.get("delta_ms")},
        mission_id=mission_id, mission_event_id=event_id, evidence_id=evidence_id)
    evidence.link_analysis(evidence_id, mission_id, created["id"])
    # Explicit analyst request; Visual Intelligence never performs a web request on this path.
    return visual_service.analyze(created["id"])
