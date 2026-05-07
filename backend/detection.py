from ultralytics import YOLO
import torch

# 🔥 Load YOLO model ONCE (important for performance)
model = YOLO("yolov8n.pt")
USE_CUDA = torch.cuda.is_available()

if USE_CUDA:
    print("✅ CUDA available: using GPU inference")
else:
    print("⚠️ CUDA not available: falling back to CPU inference")

def get_detections(frame):
    """
    Runs YOLOv8 detection on a frame using GPU.
    Returns detections in DeepSORT format:
    ([x, y, w, h], confidence, class_name)
    """

    inference_kwargs = {
        "imgsz": 640,
        "conf": 0.5,
        "verbose": False,
    }

    if USE_CUDA:
        inference_kwargs["device"] = "cuda"
        inference_kwargs["half"] = True
    else:
        inference_kwargs["device"] = "cpu"

    try:
        results = model(frame, **inference_kwargs)
    except Exception as e:
        # If CUDA path fails at runtime, retry once on CPU.
        print(f"⚠️ Detection fallback to CPU due to CUDA error: {e}")
        inference_kwargs["device"] = "cpu"
        inference_kwargs.pop("half", None)
        results = model(frame, **inference_kwargs)

    detections = []

    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0])
            cls = int(box.cls[0])

            label = model.names[cls]

            # 🎯 Filter only important classes (optional)
            if label in ["person", "car", "motorbike", "bus", "truck"]:
                w = x2 - x1
                h = y2 - y1

                detections.append(([x1, y1, w, h], conf, label))

    return detections