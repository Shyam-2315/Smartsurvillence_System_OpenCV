"""Immutable analyst captures from the shared live airborne frame."""
from __future__ import annotations

import cv2
from fastapi import HTTPException

import config
import worker
from telemetry import nearest
from . import evidence, events, service


def capture() -> dict:
    frame = worker.processed_frame_snapshot()
    if frame is None:
        raise HTTPException(409, "No processed live frame is available")
    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        raise HTTPException(500, "Could not encode live frame")
    mission = service.current_active_live_mission(config.settings.airborne_camera_id)
    association = nearest(config.settings.airborne_camera_id)
    telemetry = association["telemetry"] if association else None
    metadata = {
        "telemetry_timestamp": association["telemetry_timestamp"] if association else None,
        "delta_ms": association["delta_ms"] if association else None,
        "ground_speed_mps": telemetry.get("ground_speed_mps") if telemetry else None,
        "telemetry": telemetry,
    }
    item = evidence.create_bytes(
        data=encoded.tobytes(), filename="airborne-live-capture.jpg", source_type="airborne_live_capture",
        mission_id=mission["id"] if mission else None, camera_id=config.settings.airborne_camera_id,
        latitude=telemetry.get("latitude") if telemetry else None, longitude=telemetry.get("longitude") if telemetry else None,
        altitude_m=telemetry.get("altitude_m") if telemetry else None, heading_deg=telemetry.get("heading_deg") if telemetry else None,
        telemetry_associated=telemetry is not None, metadata=metadata,
    )
    event = None
    if mission:
        event = events.create(mission["id"], "manual_capture", camera_id=config.settings.airborne_camera_id,
                              evidence_id=item["id"], metadata=metadata)
    return {"evidence": item, "event": event, "telemetry_association": association}
