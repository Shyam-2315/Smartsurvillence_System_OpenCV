"""Single camera/AI pipeline shared by all streaming clients."""
import logging, threading, time
import cv2
from camera import CameraManager
import config
from detection import USE_CUDA, get_detections
from tracking import track_objects
from behavior import detect_loitering
from utils import save_screenshot
from notifier import send_telegram_alert, send_telegram_image
from storage import init_db, get_rule, list_zones, create_incident
from geo import bbox_center_norm, point_in_polygon
from alerting import should_create_incident
from telemetry import latest as latest_telemetry
from motion import NoOpMotionCompensator

logger = logging.getLogger(__name__)
camera = CameraManager(config.settings)
latest_frame = processed_frame = None
latest_alerts, alert_history = [], []
_stop = threading.Event(); _threads = []; _frame_lock = threading.Lock()
_alerted, _last_seen, _last_incident = set(), {}, {}
_rule, _zones, _last_config = {"enabled": True, "min_duration_sec": 10, "zone_id": None, "cooldown_sec": 30}, [], 0.0
latest_status = {"camera_online": False, "ai_online": False, "using_cuda": USE_CUDA, "telegram_enabled": config.settings.telegram_enabled and bool(config.settings.bot_token and config.settings.chat_id), "detections": 0, "tracks": 0, "active_alerts": 0, "last_inference_ms": None, "ai_fps": None, "gpu_mem_mb": None, "last_updated_ts": None}
motion_compensator = NoOpMotionCompensator()

def _set_frame(frame):
    global latest_frame
    with _frame_lock: latest_frame = frame

def _snapshot():
    with _frame_lock: return None if latest_frame is None else latest_frame.copy()

def _refresh(now):
    global _rule, _zones, _last_config
    if now - _last_config < 2: return
    _last_config = now
    try: _rule = get_rule(config.settings.database_path, "loitering") or _rule; _zones = list_zones(config.settings.database_path)
    except Exception as exc: logger.warning("configuration refresh failed: %s", exc)

def _zone_allows(bbox, width, height):
    zone_id = _rule.get("zone_id")
    if zone_id is None: return True
    zone = next((z for z in _zones if z["id"] == int(zone_id)), None)
    if not zone: return True
    x, y, w, h = bbox
    return point_in_polygon(bbox_center_norm(x, y, w, h, width, height), [(float(a), float(b)) for a,b in zone["points"]])

def camera_worker(): camera.read_loop(_set_frame)

def ai_worker():
    global processed_frame, latest_alerts
    logger.info("AI worker started"); latest_status["ai_online"] = True; previous = None
    while not _stop.is_set():
        source = _snapshot()
        if source is None: _stop.wait(.05); continue
        try:
            started = time.time(); source = motion_compensator.compensate(source); detections = get_detections(source); tracks = track_objects(detections, source); now = time.time(); _refresh(now)
            current = {track_id for track_id, *_ in tracks}
            for track_id in current: _last_seen[track_id] = now
            for track_id, seen in list(_last_seen.items()):
                if track_id not in current and now-seen > 5: _last_seen.pop(track_id, None); _alerted.discard(track_id); _last_incident.pop(track_id, None)
            alerts = detect_loitering(tracks, loiter_time_sec=float(_rule.get("min_duration_sec", 10))); latest_alerts = alerts
            for track_id, x, y, w, h in tracks:
                cv2.rectangle(source, (x,y), (x+w,y+h), (0,255,0), 2); cv2.putText(source, f"ID {track_id}", (x,y-10), cv2.FONT_HERSHEY_SIMPLEX, .6, (0,255,0), 2)
            for track_id, duration in alerts:
                bbox = next(((x,y,w,h) for ident,x,y,w,h in tracks if ident == track_id), None)
                if not _rule.get("enabled", True) or bbox is None or not _zone_allows(bbox, source.shape[1], source.shape[0]): continue
                cv2.putText(source, f"LOITERING ALERT ID {track_id}", (20,35), cv2.FONT_HERSHEY_SIMPLEX, .8, (0,0,255), 2)
                cooldown = float(_rule.get("cooldown_sec", 30))
                if not should_create_incident(track_id, _alerted, _last_incident, now, cooldown): continue
                try:
                    evidence = save_screenshot(source, track_id); filename = evidence.split("/")[-1].split("\\")[-1]
                    severity = "critical" if duration >= float(_rule["min_duration_sec"])*3 else "high" if duration >= float(_rule["min_duration_sec"])*2 else "medium"
                    create_incident(config.settings.database_path, type="Loitering", severity=severity, message=f"Loitering detected for {duration:.1f}s", camera=config.settings.camera_id, zone_id=_rule.get("zone_id"), track_id=track_id, duration_sec=duration, screenshot_filename=filename, created_at_ts=int(now), telemetry=latest_telemetry(config.settings.camera_id) if config.settings.camera_mode == "airborne" else None)
                    if latest_status["telegram_enabled"]: send_telegram_alert(f"Loitering Alert\nTrack ID: {track_id}\nDuration: {duration:.1f}s"); send_telegram_image(evidence, f"Alert - Track ID {track_id}")
                    alert_history.append({"track_id": int(track_id), "duration_sec": round(duration,2), "screenshot_path": filename, "message": "Loitering detected", "timestamp": int(now)}); del alert_history[:-50]
                    _alerted.add(track_id); _last_incident[track_id] = now; logger.warning("loitering incident track_id=%s", track_id)
                except Exception as exc: logger.exception("alert handling failed: %s", exc)
            with _frame_lock: processed_frame = source.copy()
            elapsed = time.time()-started
            latest_status.update(ai_online=True, detections=len(detections), tracks=len(tracks), active_alerts=len(alerts), last_inference_ms=round(elapsed*1000,2), ai_fps=round(1/max(.001, now-previous),2) if previous else None, last_updated_ts=int(now))
            previous = now
        except Exception as exc:
            logger.exception("AI processing error: %s", exc); latest_status["ai_online"] = False
        _stop.wait(.01)

def start():
    init_db(config.settings.database_path); _stop.clear()
    global _threads
    _threads = [threading.Thread(target=camera_worker, daemon=True, name="camera-worker"), threading.Thread(target=ai_worker, daemon=True, name="ai-worker")]
    [thread.start() for thread in _threads]

def stop():
    _stop.set(); camera.close()
    for thread in _threads: thread.join(timeout=3)

def status():
    result = dict(latest_status); result.update(camera.status()); result.update(camera_id=config.settings.camera_id, camera_name=config.settings.camera_name, camera_mode=config.settings.camera_mode, tracking_notice="Track persistence is less reliable for a moving airborne camera; no motion compensation is active." if config.settings.camera_mode == "airborne" else None); result["camera_online"] = camera.online; return result

def capture_current_frame():
    """Create immutable manual evidence from the shared processed frame."""
    import hashlib
    frame=_snapshot()
    if frame is None: raise RuntimeError("No current camera frame is available")
    now=int(time.time()); filename=f"manual_{config.settings.camera_id}_{now}.jpg"; path=__import__('pathlib').Path(config.settings.capture_directory)/filename
    if not cv2.imwrite(str(path),frame): raise RuntimeError("Could not save current frame")
    data=path.read_bytes(); telemetry=latest_telemetry(config.settings.camera_id) if config.settings.camera_mode == "airborne" else None
    incident=create_incident(config.settings.database_path,type="manual_capture",severity="low",message="Manual camera frame capture",camera=config.settings.camera_id,screenshot_filename=filename,created_at_ts=now,telemetry=telemetry)
    return {"incident":incident,"filename":filename,"sha256":hashlib.sha256(data).hexdigest(),"telemetry":telemetry}

def processed_frame_snapshot():
    """Return a copy of the frame after the shared live AI pipeline, if available."""
    with _frame_lock:
        return None if processed_frame is None else processed_frame.copy()
