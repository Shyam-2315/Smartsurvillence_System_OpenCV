import cv2
from detection import get_detections
from tracking import track_objects
from behavior import detect_loitering
from utils import save_screenshot
from alerts import log_alert

# Optional DB (safe import)
try:
    from alerts import save_alert_db
except:
    save_alert_db = None

# Telegram notifier
from notifier import send_telegram_alert, send_telegram_image

# Initialize camera
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("❌ Error: Cannot access camera")
    exit()

# Prevent duplicate alerts
saved_ids = set()

print("✅ Smart Surveillance System Started...")

while True:
    ret, frame = cap.read()
    if not ret:
        print("❌ Failed to grab frame")
        break

    # Step 1: Detection
    detections = get_detections(frame)

    # Step 2: Tracking
    tracks = track_objects(detections, frame)

    # Step 3: Behavior Detection
    alerts = detect_loitering(tracks)

    # Step 4: Draw bounding boxes
    for track_id, x, y, w, h in tracks:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(
            frame,
            f"ID {track_id}",
            (x, y - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )

    # Step 5: Handle alerts
    for track_id, duration in alerts:

        if track_id not in saved_ids:
            # 📸 Save screenshot
            file_path = save_screenshot(frame, track_id)

            # 📝 Log alert
            log_alert(track_id, duration)

            # 🗄 Save to DB (if enabled)
            if save_alert_db:
                try:
                    save_alert_db(track_id, "Loitering detected")
                except Exception as e:
                    print("DB Error:", e)

            # 📲 Send Telegram Alert
            try:
                send_telegram_alert(f"🚨 Loitering Alert!\nID: {track_id}")
                send_telegram_image(file_path, f"📸 Person ID {track_id}")
            except Exception as e:
                print("Telegram Error:", e)

            print(f"[ALERT] ID {track_id} | Saved & Sent")

            saved_ids.add(track_id)

        # Show alert on screen
        cv2.putText(
            frame,
            f"🚨 LOITERING ALERT ID {track_id}",
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            3,
        )

    # Display window
    cv2.imshow("Smart Surveillance System", frame)

    # Exit on ESC
    if cv2.waitKey(1) & 0xFF == 27:
        print("🛑 Exiting system...")
        break

# Cleanup
cap.release()
cv2.destroyAllWindows()