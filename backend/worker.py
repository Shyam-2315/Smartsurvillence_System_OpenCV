import cv2
import time

from detection import get_detections
from detection import USE_CUDA
from tracking import track_objects
from behavior import detect_loitering
from utils import save_screenshot
from alerts import log_alert, save_alert_db
from notifier import send_telegram_alert, send_telegram_image
from storage import DEFAULT_DB_PATH, init_db, get_rule, list_zones, create_incident
from geo import bbox_center_norm, point_in_polygon

latest_frame = None
processed_frame = None
latest_alerts = []
alert_history = []
alerted_track_ids = set()
last_seen_track_ts = {}
ALERT_HISTORY_LIMIT = 50
TRACK_FORGET_SECONDS = 5

CONFIG_REFRESH_SECONDS = 2
_last_config_refresh_ts = 0.0
_loiter_rule = {"enabled": True, "min_duration_sec": 10, "zone_id": None, "cooldown_sec": 30}
_zones_cache = []
_track_last_incident_ts = {}

latest_status = {
    "camera_online": False,
    "ai_online": False,
    "using_cuda": USE_CUDA,
    "detections": 0,
    "tracks": 0,
    "active_alerts": 0,
    "last_inference_ms": None,
    "ai_fps": None,
    "gpu_mem_mb": None,
    "last_updated_ts": None,
}

def _refresh_config_if_needed(now_ts: float):
    global _last_config_refresh_ts, _loiter_rule, _zones_cache
    if (now_ts - _last_config_refresh_ts) < CONFIG_REFRESH_SECONDS:
        return
    _last_config_refresh_ts = now_ts
    try:
        rule = get_rule(DEFAULT_DB_PATH, "loitering")
        if isinstance(rule, dict):
            _loiter_rule = rule
    except Exception as e:
        print("⚠️ Rule load error:", e)
    try:
        _zones_cache = list_zones(DEFAULT_DB_PATH)
    except Exception as e:
        print("⚠️ Zones load error:", e)


def _zone_allows_track(zone_id, track_bbox, frame_w: int, frame_h: int) -> bool:
    if zone_id is None:
        return True
    try:
        zone_id_int = int(zone_id)
    except Exception:
        return True
    zone = next((z for z in _zones_cache if int(z["id"]) == zone_id_int), None)
    if not zone:
        return True
    x, y, w, h = track_bbox
    cx, cy = bbox_center_norm(int(x), int(y), int(w), int(h), int(frame_w), int(frame_h))
    poly = [(float(px), float(py)) for px, py in zone.get("points", [])]
    return point_in_polygon((cx, cy), poly)


def _open_camera():
    # Prefer DirectShow on Windows to avoid intermittent MSMF issues.
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if cap.isOpened():
        return cap
    return cv2.VideoCapture(0)


def camera_worker():

    global latest_frame, latest_status

    cap = _open_camera()

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print("❌ Cannot open camera")
        latest_status["camera_online"] = False
        return

    print("📷 Camera Worker Started")
    latest_status["camera_online"] = True

    while True:

        ret, frame = cap.read()

        if not ret:
            latest_status["camera_online"] = False
            continue

        latest_frame = frame
        latest_status["camera_online"] = True

        time.sleep(0.01)


def ai_worker():

    global latest_frame, processed_frame, latest_alerts, latest_status

    print("🧠 AI Worker Started")
    latest_status["ai_online"] = True
    try:
        init_db(DEFAULT_DB_PATH)
    except Exception as e:
        print("⚠️ DB init error:", e)

    last_frame_done_ts = None
    try:
        import torch  # optional, only for GPU stats
    except Exception:
        torch = None

    while True:

        try:
            t0 = time.time()

            if latest_frame is None:
                time.sleep(0.01)
                continue

            frame = latest_frame.copy()

            # YOLO detections
            detections = get_detections(frame)

            # Tracking
            tracks = track_objects(detections, frame)
            now_ts = time.time()
            _refresh_config_if_needed(now_ts)
            current_track_ids = {track_id for track_id, *_ in tracks}
            for track_id in current_track_ids:
                last_seen_track_ts[track_id] = now_ts

            stale_ids = [
                track_id
                for track_id, ts in list(last_seen_track_ts.items())
                if track_id not in current_track_ids and (now_ts - ts) > TRACK_FORGET_SECONDS
            ]
            for track_id in stale_ids:
                last_seen_track_ts.pop(track_id, None)
                alerted_track_ids.discard(track_id)
                _track_last_incident_ts.pop(track_id, None)

            # Behavior Analysis
            loiter_min = float(_loiter_rule.get("min_duration_sec", 10))
            loitering_alerts = detect_loitering(tracks, loiter_time_sec=loiter_min)
            latest_alerts = loitering_alerts

            # Draw boxes
            for track_id, x, y, w, h in tracks:

                cv2.rectangle(
                    frame,
                    (x, y),
                    (x + w, y + h),
                    (0, 255, 0),
                    2
                )

                cv2.putText(
                    frame,
                    f"ID {track_id}",
                    (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2
                )

            # Alert Decision Engine + Actions
            for track_id, duration in loitering_alerts:
                if not bool(_loiter_rule.get("enabled", True)):
                    continue

                track_bbox = next(((_x, _y, _w, _h) for (_id, _x, _y, _w, _h) in tracks if _id == track_id), None)
                if track_bbox is not None:
                    if not _zone_allows_track(_loiter_rule.get("zone_id"), track_bbox, frame.shape[1], frame.shape[0]):
                        continue

                cv2.putText(
                    frame,
                    f"LOITERING ALERT ID {track_id}",
                    (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2,
                )

                if track_id in alerted_track_ids:
                    continue

                cooldown = float(_loiter_rule.get("cooldown_sec", 30))
                last_inc_ts = _track_last_incident_ts.get(track_id)
                if last_inc_ts is not None and (now_ts - float(last_inc_ts)) < cooldown:
                    continue

                screenshot_path = save_screenshot(frame, track_id)
                log_alert(track_id, duration)

                try:
                    save_alert_db(track_id, f"Loitering detected for {duration:.1f}s")
                except Exception as e:
                    print("⚠️ DB Error:", e)

                screenshot_filename = None
                try:
                    screenshot_filename = str(screenshot_path).replace("\\", "/").split("/")[-1]
                except Exception:
                    screenshot_filename = None

                try:
                    severity = (
                        "critical"
                        if duration >= (loiter_min * 3)
                        else "high"
                        if duration >= (loiter_min * 2)
                        else "medium"
                    )
                    create_incident(
                        DEFAULT_DB_PATH,
                        type="Loitering",
                        severity=severity,
                        message=f"Loitering detected for {duration:.1f}s",
                        camera="CAM-01",
                        zone_id=_loiter_rule.get("zone_id"),
                        track_id=int(track_id),
                        duration_sec=float(duration),
                        screenshot_filename=screenshot_filename,
                        created_at_ts=int(now_ts),
                    )
                except Exception as e:
                    print("⚠️ Incident save error:", e)

                try:
                    send_telegram_alert(
                        f"🚨 Loitering Alert\nTrack ID: {track_id}\nDuration: {duration:.1f}s"
                    )
                    send_telegram_image(
                        screenshot_path, f"📸 Alert - Track ID {track_id}"
                    )
                except Exception as e:
                    print("⚠️ Telegram Error:", e)

                alert_event = {
                    "track_id": int(track_id),
                    "duration_sec": round(float(duration), 2),
                    "screenshot_path": screenshot_path,
                    "message": "Loitering detected",
                    "timestamp": int(time.time()),
                }
                alert_history.append(alert_event)
                if len(alert_history) > ALERT_HISTORY_LIMIT:
                    del alert_history[0 : len(alert_history) - ALERT_HISTORY_LIMIT]

                alerted_track_ids.add(track_id)
                _track_last_incident_ts[track_id] = now_ts
                print(f"🚨 Alert handled for track ID {track_id}")

            # VERY IMPORTANT
            processed_frame = frame
            latest_status["ai_online"] = True
            latest_status["detections"] = len(detections)
            latest_status["tracks"] = len(tracks)
            latest_status["active_alerts"] = len(loitering_alerts)
            latest_status["last_inference_ms"] = round((time.time() - t0) * 1000, 2)
            if last_frame_done_ts is not None:
                dt = max(1e-3, float(time.time() - last_frame_done_ts))
                latest_status["ai_fps"] = round(1.0 / dt, 2)
            last_frame_done_ts = time.time()
            if USE_CUDA and torch is not None:
                try:
                    latest_status["gpu_mem_mb"] = round(float(torch.cuda.memory_allocated()) / (1024 * 1024), 2)
                except Exception:
                    latest_status["gpu_mem_mb"] = None
            latest_status["last_updated_ts"] = int(time.time())

        except Exception as e:
            print("❌ AI Error:", e)
            latest_status["ai_online"] = False
            latest_status["ai_fps"] = None
            if latest_frame is not None:
                frame = latest_frame.copy()
                cv2.putText(
                    frame,
                    "AI processing error - check logs",
                    (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2,
                )
                processed_frame = frame

        time.sleep(0.01)