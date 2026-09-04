"""Local-only aircraft telemetry state with bounded database sampling."""
import threading, time
from collections import defaultdict, deque
import config
from storage import store_telemetry
_lock=threading.Lock(); _latest={}; _last_stored={}; _history=defaultdict(lambda: deque(maxlen=128))

def ingest(camera_id, sample):
    record={"camera_id":camera_id, **sample, "_received_at": time.time()}
    if record.get("mission_id") is None:
        try:
            from airborne.service import current_active_live_mission
            active=current_active_live_mission(camera_id)
            record["mission_id"]=active["id"] if active else None
        except Exception:
            record["mission_id"]=None
    with _lock:
        _latest[camera_id]=record
        _history[camera_id].append(dict(record))
        # The legacy table requires a real coordinate: packets without GPS still
        # remain visible in latest telemetry but are never written as fake tracks.
        has_position=record.get("latitude") is not None and record.get("longitude") is not None
        if has_position and time.time()-_last_stored.get(camera_id,0) >= config.settings.airborne_telemetry_store_interval_seconds:
            store_telemetry(config.settings.database_path,record); _last_stored[camera_id]=time.time()
    return record

def latest(camera_id):
    with _lock:
        if camera_id not in _latest: return None
        result=dict(_latest[camera_id]); result.pop("_received_at", None); return result

def nearest(camera_id, captured_at: float | None = None):
    """Return only a genuinely nearby telemetry sample, never a stale location."""
    captured_at = time.time() if captured_at is None else captured_at
    with _lock:
        choices=list(_history.get(camera_id, ()))
    if not choices: return None
    candidate=min(choices, key=lambda item: abs(item["_received_at"]-captured_at))
    delta=captured_at-candidate["_received_at"]
    if abs(delta) > config.settings.airborne_telemetry_association_max_seconds: return None
    result=dict(candidate); result.pop("_received_at", None)
    return {"telemetry": result, "telemetry_timestamp": result.get("timestamp"), "delta_ms": round(delta*1000)}
