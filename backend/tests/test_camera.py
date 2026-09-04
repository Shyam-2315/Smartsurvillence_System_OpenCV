import sys
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camera import CameraManager
from config import Settings

def make_settings(source=0):
    return Settings(source, "model", .5, "db", "captures", None, None, False, [], "INFO", .01, False, None, 60, None, None, False, False)

class Capture:
    def __init__(self, frames): self.frames=list(frames); self.released=False
    def isOpened(self): return True
    def set(self, *_): pass
    def read(self): return self.frames.pop(0) if self.frames else (False, None)
    def release(self): self.released=True

def test_camera_successful_frame_and_cleanup(monkeypatch):
    manager = CameraManager(make_settings())
    capture = Capture([(True, object())]); monkeypatch.setattr(manager, "_open", lambda: capture)
    received=[]
    def on_frame(frame): received.append(frame); manager.close()
    manager.read_loop(on_frame)
    assert len(received) == 1 and capture.released and not manager.online

def test_camera_reconnect_after_disconnect(monkeypatch):
    manager = CameraManager(make_settings("rtsp://u:p@host/path")); first, second = Capture([(False, None)]), Capture([(True, object())])
    captures=iter([first, second]); monkeypatch.setattr(manager, "_open", lambda: next(captures))
    def on_frame(_): manager.close()
    manager.read_loop(on_frame)
    assert first.released and second.released and manager.reconnect_attempts == 2

def test_camera_failed_open_retries(monkeypatch):
    manager = CameraManager(make_settings())
    class Closed(Capture):
        def isOpened(self): return False
    capture=Closed([]); monkeypatch.setattr(manager, "_open", lambda: capture)
    timer=threading.Timer(.03, manager.close); timer.start(); manager.read_loop(lambda _: None)
    assert manager.reconnect_attempts >= 1 and capture.released

def test_camera_status_reports_connected_degraded_and_reconnecting():
    manager = CameraManager(make_settings(1))
    manager.online = True; manager.connection_state = "CONNECTED"
    assert manager.status()["camera_connection_state"] == "CONNECTED"
    manager.online = False; manager.last_frame_ts = __import__("time").time(); manager.connection_state = "DISCONNECTED"
    assert manager.status()["camera_connection_state"] == "DEGRADED"
    manager.last_frame_ts = None; manager.connection_state = "RECONNECTING"
    assert manager.status()["camera_connection_state"] == "RECONNECTING"
