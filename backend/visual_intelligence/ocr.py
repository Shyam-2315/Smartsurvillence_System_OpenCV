import logging
from pathlib import Path
import cv2
import config
logger = logging.getLogger(__name__)
_reader = None
_state = "OCR Ready"
_failure_notice = None

def status():
    model_dir = Path(config.settings.capture_directory) / "visual_intelligence" / "models" / "easyocr"
    if _reader is not None: return {"state":"OCR Ready", "message":"EasyOCR reader is loaded and will be reused."}
    try: import easyocr  # noqa: F401
    except ImportError: return {"state":"OCR Unavailable", "message":"EasyOCR is not installed. Install backend requirements to enable OCR."}
    if _failure_notice: return {"state":"OCR Unavailable", "message":_failure_notice}
    if not any(model_dir.rglob("*.pth")) and not config.settings.ocr_model_download_enabled:
        return {"state":"OCR Models Missing", "message":"EasyOCR model files are missing. An administrator must set OCR_MODEL_DOWNLOAD_ENABLED=true once and restart to download them."}
    return {"state":_state, "message":"EasyOCR is ready to initialize." if _state == "OCR Ready" else "EasyOCR is initializing."}

def read_with_status(image):
    """Use a project-local cache; model download is an explicit deployment choice."""
    global _reader, _state, _failure_notice
    try:
        if _reader is None:
            import easyocr
            model_dir = Path(config.settings.capture_directory) / "visual_intelligence" / "models" / "easyocr"
            model_dir.mkdir(parents=True, exist_ok=True)
            if not any(model_dir.rglob("*.pth")) and not config.settings.ocr_model_download_enabled: return [], status()["message"]
            _state = "OCR Initializing"
            _reader = easyocr.Reader(["en"], gpu=False, verbose=False, model_storage_directory=str(model_dir), user_network_directory=str(model_dir / "user_network"), download_enabled=config.settings.ocr_model_download_enabled)
        rows = _reader.readtext(image)
        _state = "OCR Completed"
        return ([{"text": str(text), "confidence": round(float(conf), 4), "box": [[round(float(x)), round(float(y))] for x, y in box]} for box, text, conf in rows], None)
    except ImportError:
        return [], "EasyOCR is not installed. Install backend requirements to enable OCR."
    except Exception as exc:
        logger.warning("OCR failed: %s", exc); _state="OCR Unavailable"; _failure_notice=f"OCR unavailable: {exc}"
        return [], _failure_notice

def read(image):
    """Backward-compatible text-only helper."""
    return read_with_status(image)[0]

def qr(image):
    value, points, _ = cv2.QRCodeDetector().detectAndDecode(image)
    return [value] if value else []
