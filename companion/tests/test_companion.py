import json
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from companion.config import CompanionSettings
from companion.health import HealthCollector
from companion.mavlink import MavlinkMonitor
from companion.transport import UdpTransport
from companion.watchdog import WatchdogState

class Stats:
    def cpu_percent(self): return 12.5
    def virtual_memory(self): return SimpleNamespace(percent=42.0)

def test_health_payload_uses_observed_stats_and_null_camera(monkeypatch, tmp_path):
    import companion.health as health
    monkeypatch.setattr(health.shutil, "disk_usage", lambda _: SimpleNamespace(free=50 * 1024 * 1024))
    monkeypatch.setattr(health, "_temperature", lambda: None)
    payload = HealthCollector(Stats(), str(tmp_path)).payload("AIR-01", {"connected": True, "heartbeat_age_seconds": 1}, None)
    assert payload["pi"]["cpu_percent"] == 12.5 and payload["pi"]["temperature_c"] is None
    assert payload["camera"]["reachable"] is None and payload["mavlink"]["connected"] is True

def test_read_only_mavlink_monitor_records_heartbeat(monkeypatch):
    import companion.mavlink as module
    class Message:
        def get_type(self): return "HEARTBEAT"
        def get_srcSystem(self): return 1
        def get_srcComponent(self): return 1
    class Connection:
        def recv_match(self, **_): return Message()
        def close(self): pass
    monkeypatch.setattr(module, "mavutil", SimpleNamespace(mavlink_connection=lambda *_args, **_kwargs: Connection()))
    monitor = MavlinkMonitor("/dev/test", 57600); monitor.poll()
    assert monitor.status()["connected"] is True and monitor.status()["system_id"] == 1

def test_udp_transport_serializes_health(monkeypatch):
    sent = []
    class Socket:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def sendto(self, data, destination): sent.append((json.loads(data), destination))
    import companion.transport as module
    monkeypatch.setattr(module.socket, "socket", lambda *_: Socket())
    UdpTransport("192.168.1.2", 14600).send({"aircraft_id": "AIR-01"})
    assert sent == [({"aircraft_id": "AIR-01"}, ("192.168.1.2", 14600))]

def test_read_only_config_and_watchdog(monkeypatch):
    monkeypatch.setenv("COMPANION_MAVLINK_READ_ONLY", "false")
    try: CompanionSettings.from_env()
    except ValueError: pass
    else: assert False
    watchdog = WatchdogState(); watchdog.failure(); assert watchdog.snapshot()["consecutive_failures"] == 1
    watchdog.success(); assert watchdog.snapshot()["consecutive_failures"] == 0
