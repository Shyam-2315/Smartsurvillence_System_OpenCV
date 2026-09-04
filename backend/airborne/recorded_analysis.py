"""Low-priority, in-process recorded mission analysis using the shared YOLO model."""
from __future__ import annotations

import json
import math
import queue
import sqlite3
import threading
import time
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
from fastapi import HTTPException

import config
from detection import get_detections
from . import evidence, events, service

_queue: queue.Queue[str] = queue.Queue()
_workers: list[threading.Thread] = []
_workers_lock = threading.Lock()
logger = logging.getLogger(__name__)


def _now() -> str: return datetime.now(timezone.utc).isoformat()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.settings.database_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _job(job_id: str) -> dict[str, Any]:
    conn = _conn()
    try: row = conn.execute("SELECT * FROM recorded_analysis_jobs WHERE id=?", (job_id,)).fetchone()
    finally: conn.close()
    if not row: raise HTTPException(404, "Recorded analysis job not found")
    return dict(row)


def status(mission_id: str) -> dict[str, Any]:
    service.get_mission(mission_id)
    conn = _conn()
    try: row = conn.execute("SELECT * FROM recorded_analysis_jobs WHERE mission_id=?", (mission_id,)).fetchone()
    finally: conn.close()
    if not row: raise HTTPException(404, "Recorded analysis has not been started")
    return dict(row)


def _update(job_id: str, **values: Any) -> None:
    if not values: return
    conn = _conn()
    try:
        assignments = ", ".join(f"{key}=?" for key in values)
        conn.execute(f"UPDATE recorded_analysis_jobs SET {assignments} WHERE id=?", (*values.values(), job_id))
        conn.commit()
    finally: conn.close()


def _terminal_update(job_id: str, status: str, mission_id: str, **values: Any) -> bool:
    """Finish a running job only if it has not been cancelled in another thread.

    Cancellation is intentionally authoritative: a final inference result must
    never turn a user-cancelled job back into COMPLETED or FAILED.
    """
    conn = _conn()
    try:
        assignments = ", ".join(f"{key}=?" for key in {"status": status, **values})
        result = conn.execute(
            f"UPDATE recorded_analysis_jobs SET {assignments} WHERE id=? AND status='PROCESSING'",
            (status, *values.values(), job_id),
        )
        conn.commit()
    finally:
        conn.close()
    if result.rowcount:
        _set_mission_status(mission_id, status)
        return True
    return False


def _set_mission_status(mission_id: str, processing_status: str) -> None:
    conn = _conn()
    try:
        conn.execute("UPDATE missions SET processing_status=? WHERE id=?", (processing_status, mission_id)); conn.commit()
    finally: conn.close()


def _cancelled(job_id: str) -> bool: return _job(job_id)["status"] == "CANCELLED"


def _ensure_workers() -> None:
    with _workers_lock:
        wanted = config.settings.recorded_analysis_max_concurrent_jobs
        while len([worker for worker in _workers if worker.is_alive()]) < wanted:
            worker = threading.Thread(target=_worker, daemon=True, name="recorded-analysis-worker")
            _workers.append(worker); worker.start()


def start(mission_id: str) -> dict[str, Any]:
    mission = service.get_mission(mission_id)
    if mission["source_type"] != "recorded": raise HTTPException(409, "Only recorded missions can be analyzed")
    service.recorded_video_path(mission_id)
    job_id = str(uuid.uuid4())
    conn = _conn()
    try:
        existing = conn.execute("SELECT id FROM recorded_analysis_jobs WHERE mission_id=?", (mission_id,)).fetchone()
        if existing: raise HTTPException(409, "Recorded mission analysis already exists")
        conn.execute("INSERT INTO recorded_analysis_jobs (id,mission_id,status,created_at) VALUES (?,?,?,?)", (job_id, mission_id, "QUEUED", _now()))
        conn.commit()
    finally: conn.close()
    _set_mission_status(mission_id, "QUEUED")
    _ensure_workers(); _queue.put(job_id)
    return _job(job_id)


def cancel(mission_id: str) -> dict[str, Any]:
    job = status(mission_id)
    conn = _conn()
    try:
        result = conn.execute(
            "UPDATE recorded_analysis_jobs SET status='CANCELLED', ended_at=? "
            "WHERE id=? AND status IN ('QUEUED', 'PROCESSING')",
            (_now(), job["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    if not result.rowcount:
        raise HTTPException(409, "Analysis job is already finished")
    _set_mission_status(mission_id, "CANCELLED")
    return _job(job["id"])


def _store_sample(job_id: str, timestamp: float, frame_index: int, rows: list[dict[str, Any]]) -> None:
    conn = _conn()
    try:
        conn.execute("INSERT INTO recorded_frame_detections (id,job_id,video_timestamp_seconds,frame_index,detections_json) VALUES (?,?,?,?,?)", (str(uuid.uuid4()), job_id, timestamp, frame_index, json.dumps(rows)))
        conn.commit()
    finally: conn.close()


def _persist_event(job_id: str, mission_id: str, group: dict[str, Any]) -> None:
    """Write exactly one representative evidence original for a grouped event."""
    ok, encoded = cv2.imencode(".jpg", group["frame"])
    if not ok: raise RuntimeError("Could not encode representative evidence frame")
    item = evidence.create_bytes(data=encoded.tobytes(), filename="recorded-event.jpg", source_type="recorded_detection", mission_id=mission_id)
    event_id = str(uuid.uuid4())
    conn = _conn()
    try:
        conn.execute("INSERT INTO recorded_analysis_events (id,job_id,mission_id,object_class,start_seconds,end_seconds,peak_confidence,representative_frame_index,evidence_id) VALUES (?,?,?,?,?,?,?,?,?)", (event_id, job_id, mission_id, group["object_class"], group["start"], group["end"], group["peak"], group["frame_index"], item["id"]))
        conn.commit()
    finally: conn.close()
    events.create(mission_id, "recorded_detection", evidence_id=item["id"], metadata={"recorded_event_id": event_id, "object_class": group["object_class"], "start_seconds": group["start"], "end_seconds": group["end"], "peak_confidence": group["peak"]})


def recover_interrupted_jobs() -> None:
    """In-process jobs cannot survive a server restart, so fail them explicitly."""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT id, mission_id FROM recorded_analysis_jobs WHERE status IN ('QUEUED', 'PROCESSING')"
        ).fetchall()
        if rows:
            conn.execute(
                "UPDATE recorded_analysis_jobs SET status='FAILED', error_message=?, ended_at=? "
                "WHERE status IN ('QUEUED', 'PROCESSING')",
                ("Server restarted before recorded analysis could finish", _now()),
            )
            conn.commit()
    finally:
        conn.close()
    for row in rows:
        _set_mission_status(row["mission_id"], "FAILED")


def _run(job_id: str) -> None:
    job = _job(job_id)
    if job["status"] == "CANCELLED": return
    mission_id = job["mission_id"]
    _update(job_id, status="PROCESSING", started_at=_now()); _set_mission_status(mission_id, "PROCESSING")
    capture = cv2.VideoCapture(str(service.recorded_video_path(mission_id)))
    groups: dict[str, dict[str, Any]] = {}
    try:
        if not capture.isOpened(): raise RuntimeError("Stored mission video cannot be opened")
        source_fps = capture.get(cv2.CAP_PROP_FPS)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if source_fps <= 0 or frame_count <= 0: raise RuntimeError("Stored mission video metadata cannot be read")
        stride = max(1, round(source_fps / config.settings.recorded_analysis_sample_fps))
        estimated = math.ceil(frame_count / stride); _update(job_id, estimated_samples=estimated)
        processed = 0
        for index in range(0, frame_count, stride):
            if _cancelled(job_id): return
            capture.set(cv2.CAP_PROP_POS_FRAMES, index); readable, frame = capture.read()
            if not readable: continue
            timestamp = index / source_fps
            # Deliberately yield before requesting the shared inference lock so
            # the live worker gets a recurring opportunity to run first.
            time.sleep(.01)
            raw = get_detections(frame)  # shared model + shared inference lock; never load another model.
            if _cancelled(job_id): return
            by_class: dict[str, tuple[list[int], float]] = {}
            for bbox, confidence, label in raw:
                if label not in by_class or confidence > by_class[label][1]: by_class[label] = (bbox, confidence)
            rows = [{"class": label, "confidence": confidence, "bbox": bbox} for label, (bbox, confidence) in by_class.items()]
            _store_sample(job_id, timestamp, index, rows)
            for label, (_bbox, confidence) in by_class.items():
                group = groups.get(label)
                if group and timestamp - group["last"] <= config.settings.recorded_event_merge_gap_seconds:
                    group["end"] = group["last"] = timestamp
                    if confidence > group["peak"]: group.update(peak=confidence, frame=frame.copy(), frame_index=index)
                else:
                    if group:
                        if _cancelled(job_id): return
                        _persist_event(job_id, mission_id, group)
                    groups[label] = {"object_class": label, "start": timestamp, "end": timestamp, "last": timestamp, "peak": confidence, "frame": frame.copy(), "frame_index": index}
            processed += 1
            _update(job_id, frames_processed=processed, progress_percent=round(100 * processed / estimated, 2))
            time.sleep(.01)  # give live surveillance recurring chances to acquire inference_lock.
        if _cancelled(job_id): return
        for group in groups.values():
            if _cancelled(job_id): return
            _persist_event(job_id, mission_id, group)
        conn = _conn()
        try: count = conn.execute("SELECT COUNT(*) FROM recorded_analysis_events WHERE job_id=?", (job_id,)).fetchone()[0]
        finally: conn.close()
        _terminal_update(job_id, "COMPLETED", mission_id, progress_percent=100, events_found=count, ended_at=_now())
    except Exception as exc:
        _terminal_update(job_id, "FAILED", mission_id, error_message=str(exc)[:1000], ended_at=_now())
    finally: capture.release()


def _worker() -> None:
    while True:
        try:
            _run(_queue.get())
        except Exception:
            # A worker must remain available even if a stale/corrupt queued item fails.
            logger.exception("Recorded analysis worker item failed")
        finally:
            _queue.task_done()
