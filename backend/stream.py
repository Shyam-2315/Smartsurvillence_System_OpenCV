import logging
import time
import cv2
import worker
logger = logging.getLogger(__name__)

def generate_frames():
    """Encode the latest shared AI frame; clients never start their own pipeline."""
    try:
        while True:
            frame = worker.processed_frame
            if frame is None:
                time.sleep(.1)
                continue
            ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ok:
                logger.warning("JPEG encoding failed")
                time.sleep(.1)
                continue
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
    except (GeneratorExit, KeyboardInterrupt):
        logger.debug("MJPEG client stream closed")
        return
