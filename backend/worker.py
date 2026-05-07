import cv2
import time

from detection import get_detections
from detection import USE_CUDA
from tracking import track_objects
from behavior import detect_loitering
from utils import save_screenshot
from alerts import log_alert, save_alert_db
from notifier import send_telegram_alert, send_telegram_image

latest_frame = None
processed_frame = None
latest_alerts = []
alert_history = []
alerted_track_ids = set()
last_seen_track_ts = {}
ALERT_HISTORY_LIMIT = 50
TRACK_FORGET_SECONDS = 5
latest_status = {
    "camera_online": False,
    "ai_online": False,
    "using_cuda": USE_CUDA,
    "detections": 0,
    "tracks": 0,
    "active_alerts": 0,
    "last_inference_ms": None,
    "last_updated_ts": None,
}


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

            # Behavior Analysis
            loitering_alerts = detect_loitering(tracks)
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

                screenshot_path = save_screenshot(frame, track_id)
                log_alert(track_id, duration)

                try:
                    save_alert_db(track_id, f"Loitering detected for {duration:.1f}s")
                except Exception as e:
                    print("⚠️ DB Error:", e)

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
                print(f"🚨 Alert handled for track ID {track_id}")

            # VERY IMPORTANT
            processed_frame = frame
            latest_status["ai_online"] = True
            latest_status["detections"] = len(detections)
            latest_status["tracks"] = len(tracks)
            latest_status["active_alerts"] = len(loitering_alerts)
            latest_status["last_inference_ms"] = round((time.time() - t0) * 1000, 2)
            latest_status["last_updated_ts"] = int(time.time())

        except Exception as e:
            print("❌ AI Error:", e)
            latest_status["ai_online"] = False
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