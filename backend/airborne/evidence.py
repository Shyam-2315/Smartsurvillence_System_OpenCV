"""Immutable mission-evidence storage, using only safe relative paths externally."""
from __future__ import annotations

import hashlib
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException
import config

ROOT = Path(config.settings.capture_directory).resolve() / "airborne_evidence"


def _root() -> Path:
    # Resolve dynamically so test configuration changes are honored.
    return Path(config.settings.capture_directory).resolve() / "airborne_evidence"


def _safe(relative_path: str) -> Path:
    root = _root()
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise HTTPException(404, "Evidence file not found")
    return path


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.settings.database_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize(row: sqlite3.Row) -> dict[str, Any]:
    value = dict(row)
    value["metadata"] = __import__("json").loads(value.pop("metadata_json", "{}") or "{}")
    value.pop("original_path", None)  # Never expose local filesystem paths.
    value["telemetry_associated"] = bool(value["telemetry_associated"])
    value["original_available"] = _safe(row["original_path"]).is_file()
    return value


def create_bytes(*, data: bytes, filename: str, source_type: str, mission_id: str | None = None,
                 camera_id: str | None = None, capture_timestamp: str | None = None,
                 incident_id: int | None = None, analysis_id: str | None = None,
                 latitude: float | None = None, longitude: float | None = None,
                 altitude_m: float | None = None, heading_deg: float | None = None,
                 telemetry_associated: bool = False, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Persist original bytes once; callers only receive safe metadata."""
    if not data:
        raise HTTPException(422, "Evidence bytes cannot be empty")
    evidence_id = str(uuid.uuid4())
    suffix = Path(filename).suffix.lower() or ".bin"
    if not suffix.replace(".", "").isalnum() or len(suffix) > 16:
        suffix = ".bin"
    relative = f"originals/{evidence_id}{suffix}"
    target = _safe(relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    # target is a new UUID path: evidence originals are never overwritten.
    target.write_bytes(data)
    now = _now()
    capture_timestamp = capture_timestamp or now
    sha256 = hashlib.sha256(data).hexdigest()
    conn = _conn()
    try:
        conn.execute("""INSERT INTO mission_evidence
            (id,mission_id,camera_id,created_at,capture_timestamp,source_type,original_path,sha256,
             incident_id,analysis_id,latitude,longitude,altitude_m,heading_deg,telemetry_associated,metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (evidence_id, mission_id, camera_id, now, capture_timestamp, source_type, relative, sha256,
             incident_id, analysis_id, latitude, longitude, altitude_m, heading_deg, int(telemetry_associated), __import__("json").dumps(metadata or {})))
        conn.commit()
        row = conn.execute("SELECT * FROM mission_evidence WHERE id=?", (evidence_id,)).fetchone()
    finally:
        conn.close()
    result = _serialize(row)
    if mission_id:
        # Link the durable original to its mission timeline without exposing it.
        from . import events
        events.create(mission_id, "evidence_created", camera_id=camera_id, evidence_id=evidence_id,
                      metadata={"source_type": source_type, "sha256": sha256})
    return result


def list_for_mission(mission_id: str) -> list[dict[str, Any]]:
    conn = _conn()
    try:
        rows = conn.execute("SELECT * FROM mission_evidence WHERE mission_id=? ORDER BY created_at DESC", (mission_id,)).fetchall()
    finally:
        conn.close()
    return [_serialize(row) for row in rows]


def original_path(evidence_id: str) -> Path:
    """Resolve an immutable original only after looking it up by its opaque ID."""
    conn = _conn()
    try:
        row = conn.execute("SELECT original_path FROM mission_evidence WHERE id=?", (evidence_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, "Evidence file not found")
    path = _safe(row["original_path"])
    if not path.is_file():
        raise HTTPException(404, "Evidence file not found")
    return path


def record_for_mission(evidence_id: str, mission_id: str) -> dict[str, Any]:
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM mission_evidence WHERE id=? AND mission_id=?", (evidence_id, mission_id)).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, "Mission evidence not found")
    result = dict(row)
    path = _safe(result["original_path"])
    if not path.is_file():
        raise HTTPException(404, "Evidence file not found")
    result["_path"] = path
    return result


def link_analysis(evidence_id: str, mission_id: str | None, analysis_id: str) -> None:
    conn = _conn()
    try:
        result = conn.execute("UPDATE mission_evidence SET analysis_id=? WHERE id=? AND mission_id IS ?", (analysis_id, evidence_id, mission_id))
        if not result.rowcount:
            raise HTTPException(404, "Mission evidence not found")
        if mission_id: conn.execute("UPDATE mission_events SET analysis_id=? WHERE mission_id=? AND evidence_id=?", (analysis_id, mission_id, evidence_id))
        conn.commit()
    finally:
        conn.close()
