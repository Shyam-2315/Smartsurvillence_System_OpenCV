import logging
import threading
import torch
from ultralytics import YOLO
from config import settings

logger = logging.getLogger(__name__)
model = YOLO(settings.yolo_model)  # loaded once for the shared pipeline
inference_lock = threading.Lock()  # Ultralytics model inference is shared by live and still-image work.
USE_CUDA = torch.cuda.is_available()
logger.info("YOLO loaded model=%s device=%s", settings.yolo_model, "cuda" if USE_CUDA else "cpu")

def get_detections(frame):
    kwargs = {"imgsz": 640, "conf": settings.confidence_threshold, "verbose": False, "device": "cuda" if USE_CUDA else "cpu"}
    if USE_CUDA: kwargs["half"] = True
    try:
        with inference_lock: results = model(frame, **kwargs)
    except Exception as exc:
        if not USE_CUDA: raise
        logger.warning("CUDA inference failed; retrying CPU: %s", exc)
        kwargs.pop("half", None); kwargs["device"] = "cpu"
        with inference_lock: results = model(frame, **kwargs)
    detections = []
    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0]); label = model.names[int(box.cls[0])]
            if label in {"person", "car", "motorbike", "bus", "truck"}:
                detections.append(([x1, y1, x2 - x1, y2 - y1], float(box.conf[0]), label))
    return detections
