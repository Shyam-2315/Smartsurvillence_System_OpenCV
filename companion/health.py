from __future__ import annotations
import os, shutil, socket
from datetime import datetime, timezone
from urllib.parse import urlparse
from typing import Any

def _temperature() -> float | None:
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", encoding="utf-8") as source: return round(int(source.read().strip()) / 1000, 1)
    except (OSError, ValueError): return None

def camera_reachable(source: str | None) -> bool | None:
    if not source: return None
    parsed = urlparse(source)
    if parsed.hostname:
        try:
            with socket.create_connection((parsed.hostname, parsed.port or 554), timeout=2): return True
        except OSError: return False
    return os.path.exists(source)

class HealthCollector:
    def __init__(self, stats: Any, disk_path: str = "/") -> None: self.stats, self.disk_path = stats, disk_path
    def payload(self, aircraft_id: str, mavlink: dict[str, Any], camera_source: str | None) -> dict[str, Any]:
        usage = shutil.disk_usage(self.disk_path)
        return {"aircraft_id": aircraft_id, "timestamp": datetime.now(timezone.utc).isoformat(),
                "pi": {"online": True, "cpu_percent": self.stats.cpu_percent(), "memory_percent": self.stats.virtual_memory().percent,
                       "temperature_c": _temperature(), "disk_free_mb": round(usage.free / 1024 / 1024, 1)},
                "camera": {"reachable": camera_reachable(camera_source)}, "mavlink": mavlink}
