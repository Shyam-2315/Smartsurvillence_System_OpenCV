from __future__ import annotations

import hashlib
import os
import sqlite3
import stat
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
import cv2
import config
from . import events
from .models import MISSION_SOURCE_TYPES, VALID_TRANSITIONS


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.settings.database_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def create_mission(*, name: str, source_type: str, camera_id: str | None = None, notes: str | None = None) -> dict[str, Any]:
    if source_type not in MISSION_SOURCE_TYPES:
        raise HTTPException(422, "source_type must be 'live' or 'recorded'")
    mission_id, created_at = str(uuid.uuid4()), _now()
    conn = _conn()
    try:
        conn.execute("INSERT INTO missions (id,name,source_type,camera_id,created_at,status,notes) VALUES (?,?,?,?,?,?,?)",
                     (mission_id, name.strip(), source_type, camera_id, created_at, "planned", notes))
        conn.commit()
        row = conn.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
    finally:
        conn.close()
    return _serialize(row)


def _storage_root() -> Path:
    root = Path(config.settings.recorded_mission_storage).resolve()
    for directory in (root / "originals", root / "frames", root / "thumbnails", root / "reports"):
        directory.mkdir(parents=True, exist_ok=True)
    return root


def _probe_video(path: Path) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened(): raise ValueError("Video cannot be opened")
        width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps, frame_count = float(capture.get(cv2.CAP_PROP_FPS)), int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        readable, _frame = capture.read()
        if not readable or width <= 0 or height <= 0 or fps <= 0 or frame_count <= 0:
            raise ValueError("Video metadata or frames cannot be read")
        return {"width": width, "height": height, "fps": fps, "frame_count": frame_count, "duration_seconds": frame_count / fps}
    finally: capture.release()


async def create_recorded_mission(*, name: str, upload: Any, notes: str | None = None) -> dict[str, Any]:
    """Stream an upload to staging, verify OpenCV can read it, then atomically publish it."""
    extension = Path(upload.filename or "").suffix.lower()
    if extension not in {".mp4", ".mov", ".avi", ".mkv"}: raise HTTPException(415, "Supported video formats: .mp4, .mov, .avi, .mkv")
    root = _storage_root(); token = str(uuid.uuid4())
    staging, destination = root / "originals" / f".{token}.uploading", root / "originals" / f"{token}{extension}"
    maximum, total, digest = config.settings.recorded_mission_max_upload_mb * 1024 * 1024, 0, hashlib.sha256()
    try:
        with staging.open("xb") as output:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > maximum: raise HTTPException(413, f"Upload exceeds {config.settings.recorded_mission_max_upload_mb} MB limit")
                digest.update(chunk); output.write(chunk)
        metadata = _probe_video(staging)
        os.replace(staging, destination); destination.chmod(stat.S_IREAD)
        mission_id, created_at = str(uuid.uuid4()), _now()
        conn = _conn()
        try:
            conn.execute("""INSERT INTO missions (id,name,source_type,created_at,status,notes,original_video_path,original_video_sha256,duration_seconds,fps,width,height,frame_count,processing_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (mission_id, name.strip(), "recorded", created_at, "planned", notes, str(destination.relative_to(root)), digest.hexdigest(), metadata["duration_seconds"], metadata["fps"], metadata["width"], metadata["height"], metadata["frame_count"], "ready"))
            conn.commit(); row = conn.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
        finally: conn.close()
        return _serialize(row)
    except HTTPException: raise
    except (OSError, ValueError, cv2.error): raise HTTPException(422, "Invalid or corrupt video file")
    finally:
        await upload.close()
        if staging.exists(): staging.unlink(missing_ok=True)


def recorded_video_path(mission_id: str) -> Path:
    mission = get_mission(mission_id)
    if mission["source_type"] != "recorded" or not mission.get("original_video_path"): raise HTTPException(404, "Recorded mission video not found")
    root = _storage_root(); path = (root / mission["original_video_path"]).resolve()
    try: path.relative_to(root / "originals")
    except ValueError: raise HTTPException(404, "Recorded mission video not found")
    if not path.is_file(): raise HTTPException(404, "Recorded mission video not found")
    return path


def get_mission(mission_id: str) -> dict[str, Any]:
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, "Mission not found")
    return _serialize(row)


def list_missions(*, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    conn = _conn()
    try:
        rows = conn.execute("SELECT * FROM missions ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                            (max(1, min(limit, 200)), max(0, offset))).fetchall()
    finally:
        conn.close()
    return [_serialize(row) for row in rows]


def current_active_live_mission(camera_id: str | None = None) -> dict[str, Any] | None:
    """Return the active live mission for a camera, if one is currently running."""
    conn = _conn()
    try:
        if camera_id is None:
            row = conn.execute("SELECT * FROM missions WHERE source_type='live' AND status='active' ORDER BY started_at DESC LIMIT 1").fetchone()
        else:
            row = conn.execute("SELECT * FROM missions WHERE source_type='live' AND status='active' AND camera_id=? ORDER BY started_at DESC LIMIT 1", (camera_id,)).fetchone()
    finally:
        conn.close()
    return _serialize(row) if row else None


def transition_mission(mission_id: str, target_status: str) -> dict[str, Any]:
    mission = get_mission(mission_id)
    event_type = VALID_TRANSITIONS.get(mission["status"], {}).get(target_status)
    if not event_type:
        raise HTTPException(409, f"Cannot transition mission from {mission['status']} to {target_status}")
    if target_status == "active" and mission["source_type"] == "live":
        existing = current_active_live_mission(mission["camera_id"])
        if existing and existing["id"] != mission_id:
            raise HTTPException(409, "An active live mission already exists for this camera")
    now = _now()
    conn = _conn()
    try:
        if target_status == "active":
            cur = conn.execute("UPDATE missions SET status=?, started_at=? WHERE id=? AND status='planned'", (target_status, now, mission_id))
        else:
            cur = conn.execute("UPDATE missions SET status=?, ended_at=? WHERE id=? AND status='active'", (target_status, now, mission_id))
        if cur.rowcount != 1:
            raise HTTPException(409, "Mission state changed; retry the operation")
        conn.commit()
        row = conn.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
    finally:
        conn.close()
    events.create(mission_id, event_type, camera_id=mission["camera_id"], metadata={"previous_status": mission["status"], "status": target_status})
    return _serialize(row)
