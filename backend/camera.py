from __future__ import annotations
import logging, threading, time
from typing import Any
import cv2
from config import Settings, safe_source_label
logger = logging.getLogger(__name__)

class CameraManager:
    """One capture owner; reconnects independently of the web server."""
    def __init__(self, config: Settings):
        self.config, self.source, self._capture = config, config.camera_source, None
        self._lock, self._stop = threading.Lock(), threading.Event()
        self.online = False; self.last_frame_ts: float | None = None; self.reconnect_attempts = 0
        self.connection_state = "DISCONNECTED"
    def _open(self):
        cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW) if isinstance(self.source, int) and hasattr(cv2, "CAP_DSHOW") else cv2.VideoCapture(self.source)
        if isinstance(self.source, int): cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640); cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        return cap
    def read_loop(self, on_frame) -> None:
        logger.info("camera worker started source=%s", safe_source_label(self.source))
        while not self._stop.is_set():
            if self._capture is None:
                self.connection_state = "CONNECTING" if self.reconnect_attempts == 0 else "RECONNECTING"
                self.reconnect_attempts += 1; cap = self._open()
                if not cap.isOpened():
                    cap.release(); self.online = False; self.connection_state = "DISCONNECTED"; logger.warning("camera unavailable source=%s attempt=%d", safe_source_label(self.source), self.reconnect_attempts); self._stop.wait(self.config.camera_retry_seconds); continue
                with self._lock: self._capture = cap
                self.online = True; self.connection_state = "CONNECTED"; logger.info("camera connected source=%s", safe_source_label(self.source))
            ok, frame = self._capture.read()
            if ok and frame is not None:
                self.online = True; self.last_frame_ts = time.time(); on_frame(frame); self._stop.wait(.005); continue
            self.online = False; self.connection_state = "DISCONNECTED"; logger.warning("camera disconnected source=%s", safe_source_label(self.source))
            with self._lock: old, self._capture = self._capture, None
            if old is not None: old.release()
            self._stop.wait(self.config.camera_retry_seconds)
        self.close()
    def close(self) -> None:
        self._stop.set()
        with self._lock: cap, self._capture = self._capture, None
        if cap is not None: cap.release()
        self.online = False; self.connection_state = "DISCONNECTED"
    def status(self) -> dict[str, Any]:
        state = self.connection_state
        if not self.online and self.last_frame_ts and time.time() - self.last_frame_ts < self.config.camera_retry_seconds:
            state = "DEGRADED"
        return {"configured_source": safe_source_label(self.source), "camera_online": self.online, "camera_connection_state": state, "last_frame_ts": int(self.last_frame_ts) if self.last_frame_ts else None, "reconnect_attempts": self.reconnect_attempts}
