from ultralytics import YOLO
import cv2

# Load model
model = YOLO("yolov8n.pt")  # auto-downloads

def detect_objects(frame):
    results = model(frame)

    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0])
            cls = int(box.cls[0])

            label = model.names[cls]

            if conf > 0.5:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0,255,0), 2)
                cv2.putText(frame, f"{label} {conf:.2f}", 
                            (x1, y1-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 
                            0.5, (0,255,0), 2)

    return frame

def get_detections(frame):
    results = model(frame)

    detections = []

    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0])

            if conf > 0.5:
                detections.append(([x1, y1, x2-x1, y2-y1], conf, 'person'))

    return detections