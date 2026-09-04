"""Analyst-triggered bridge from immutable recorded evidence into Visual Intelligence."""
from __future__ import annotations

import json
import math
import sqlite3
from typing import Any

import cv2
from fastapi import HTTPException

import config
from . import evidence, events, service


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.settings.database_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _recorded_mission(mission_id: str) -> dict[str, Any]:
    mission = service.get_mission(mission_id)
    if mission["source_type"] != "recorded":
        raise HTTPException(409, "Only recorded mission video frames can be extracted")
    return mission


def extract_frame(mission_id: str, timestamp_seconds: float) -> dict[str, Any]:
    mission = _recorded_mission(mission_id)
    if not math.isfinite(timestamp_seconds) or timestamp_seconds < 0 or timestamp_seconds >= (mission.get("duration_seconds") or 0):
        raise HTTPException(422, "timestamp_seconds must be within the recorded video duration")
    capture = cv2.VideoCapture(str(service.recorded_video_path(mission_id)))
    try:
        capture.set(cv2.CAP_PROP_POS_MSEC, timestamp_seconds * 1000)
        readable, frame = capture.read()
        if not readable:
            raise HTTPException(422, "Could not extract a frame at the requested timestamp")
        ok, encoded = cv2.imencode(".jpg", frame)
        if not ok:
            raise HTTPException(500, "Could not encode extracted frame")
    finally:
        capture.release()
    item = evidence.create_bytes(data=encoded.tobytes(), filename="recorded-manual-frame.jpg", source_type="recorded_manual_frame", mission_id=mission_id)
    event = events.create(mission_id, "manual_capture", evidence_id=item["id"], metadata={"video_timestamp_seconds": timestamp_seconds})
    return {"evidence": item, "event": event}


def _event_context(mission_id: str, evidence_id: str) -> tuple[str | None, float | None]:
    conn = _conn()
    try:
        row = conn.execute("SELECT id, metadata_json FROM mission_events WHERE mission_id=? AND evidence_id=? ORDER BY timestamp DESC LIMIT 1", (mission_id, evidence_id)).fetchone()
    finally:
        conn.close()
    if not row:
        return None, None
    metadata = json.loads(row["metadata_json"] or "{}")
    timestamp = metadata.get("video_timestamp_seconds", metadata.get("start_seconds"))
    return row["id"], float(timestamp) if isinstance(timestamp, (int, float)) else None


def investigate_evidence(mission_id: str, evidence_id: str) -> dict[str, Any]:
    _recorded_mission(mission_id)
    item = evidence.record_for_mission(evidence_id, mission_id)
    # Reopen an existing linked analysis rather than creating competing copies.
    from visual_intelligence import service as visual_service
    if item.get("analysis_id"):
        return visual_service.get(item["analysis_id"])
    event_id, video_timestamp_seconds = _event_context(mission_id, evidence_id)
    source_context = {
        "mission_id": mission_id,
        "mission_event_id": event_id,
        "evidence_id": evidence_id,
        "video_timestamp_seconds": video_timestamp_seconds,
    }
    created = visual_service.create_bytes(
        item["_path"].read_bytes(), "recorded-mission-evidence.jpg", source_type="recorded_mission",
        source_metadata=source_context, mission_id=mission_id, mission_event_id=event_id,
        evidence_id=evidence_id, video_timestamp_seconds=video_timestamp_seconds,
    )
    evidence.link_analysis(evidence_id, mission_id, created["id"])
    # This is an explicit analyst action.  The recorded scan itself never invokes OCR or web search.
    return visual_service.analyze(created["id"])
