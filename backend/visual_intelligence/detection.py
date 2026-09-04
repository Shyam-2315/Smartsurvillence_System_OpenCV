import logging
logger = logging.getLogger(__name__)

def detect(image):
    try:
        from detection import model, USE_CUDA, inference_lock
        with inference_lock:
            results = model(image, imgsz=640, conf=.25, verbose=False, device="cuda" if USE_CUDA else "cpu")
        items=[]
        for result in results:
            for box in result.boxes:
                x1,y1,x2,y2 = [round(float(x)) for x in box.xyxy[0].tolist()]
                items.append({"class": str(model.names[int(box.cls[0])]), "confidence": round(float(box.conf[0]),4), "bbox": [x1,y1,x2,y2]})
        return items
    except Exception as exc:
        logger.warning("Visual object detection unavailable: %s", exc); return []
