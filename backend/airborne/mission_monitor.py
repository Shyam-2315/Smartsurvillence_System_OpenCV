"""Debounced live-mission state transition events; never controls the aircraft."""
from __future__ import annotations
import threading

import config
import worker
from mavlink_service import service as mavlink_service
from . import events, service

_stop = threading.Event(); _thread: threading.Thread | None = None; _last: dict[str, tuple[bool | None, bool | None]] = {}

def _run() -> None:
    while not _stop.wait(1):
        mission = service.current_active_live_mission(config.settings.airborne_camera_id)
        if not mission: continue
        video = bool(worker.camera.online)
        telemetry_state = mavlink_service.status()["state"]
        telemetry_ok = telemetry_state == "CONNECTED"
        previous = _last.get(mission["id"])
        if previous is not None:
            if previous[0] and not video: events.create(mission["id"], "video_lost", camera_id=config.settings.airborne_camera_id)
            elif not previous[0] and video: events.create(mission["id"], "video_restored", camera_id=config.settings.airborne_camera_id)
            if config.settings.mavlink_enabled:
                if previous[1] and not telemetry_ok: events.create(mission["id"], "telemetry_stale", camera_id=config.settings.airborne_camera_id, metadata={"state": telemetry_state})
                elif not previous[1] and telemetry_ok: events.create(mission["id"], "telemetry_restored", camera_id=config.settings.airborne_camera_id)
        _last[mission["id"]] = (video, telemetry_ok)

def start() -> None:
    global _thread
    if _thread and _thread.is_alive(): return
    _stop.clear(); _thread = threading.Thread(target=_run, daemon=True, name="airborne-mission-monitor"); _thread.start()

def stop() -> None:
    _stop.set()
    if _thread: _thread.join(timeout=2)
