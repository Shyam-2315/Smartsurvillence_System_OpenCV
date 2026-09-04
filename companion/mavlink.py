"""Read-only heartbeat monitor. It never obtains a MAVLink sender or emits packets."""
from __future__ import annotations
import time
from typing import Any
try:
    from pymavlink import mavutil
except ImportError: mavutil = None

class MavlinkMonitor:
    def __init__(self, connection: str, baud: int) -> None:
        self.connection_name, self.baud, self.connection, self.last_heartbeat = connection, baud, None, None
        self.system_id: int | None = None; self.component_id: int | None = None
    def connect(self) -> None:
        if mavutil is None: raise RuntimeError("pymavlink is not installed")
        self.connection = mavutil.mavlink_connection(self.connection_name, baud=self.baud, autoreconnect=False)
    def poll(self, timeout: float = 1.0) -> None:
        if self.connection is None: self.connect()
        message = self.connection.recv_match(blocking=True, timeout=timeout)
        if message is None or message.get_type() != "HEARTBEAT": return
        self.last_heartbeat = time.time()
        for attr, target in (("get_srcSystem", "system_id"), ("get_srcComponent", "component_id")):
            try: setattr(self, target, int(getattr(message, attr)()))
            except (AttributeError, TypeError, ValueError): pass
    def status(self) -> dict[str, Any]:
        age = None if self.last_heartbeat is None else round(max(0, time.time() - self.last_heartbeat), 2)
        return {"connected": self.last_heartbeat is not None and age is not None and age <= 5, "heartbeat_age_seconds": age,
                "system_id": self.system_id, "component_id": self.component_id}
    def close(self) -> None:
        if self.connection is not None:
            try: self.connection.close()
            except Exception: pass
        self.connection = None
