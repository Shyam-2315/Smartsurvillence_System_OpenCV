from __future__ import annotations
import logging, time
from logging.handlers import RotatingFileHandler
from pathlib import Path
import psutil
from .config import CompanionSettings
from .health import HealthCollector
from .mavlink import MavlinkMonitor
from .transport import HttpTransport, UdpTransport
from .watchdog import WatchdogState

def configure_logging(settings: CompanionSettings) -> None:
    path = Path(settings.log_file); path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[RotatingFileHandler(path, maxBytes=settings.log_max_bytes, backupCount=settings.log_backups), logging.StreamHandler()], format="%(asctime)s %(levelname)s %(message)s")

def main() -> int:
    settings = CompanionSettings.from_env(); configure_logging(settings); log = logging.getLogger(__name__)
    monitor = MavlinkMonitor(settings.mavlink_connection, settings.mavlink_baud)
    collector = HealthCollector(psutil)
    watchdog = WatchdogState()
    if settings.transport == "http":
        if not settings.ground_health_url or not settings.ground_device_key: raise ValueError("HTTP transport requires ground URL and device key")
        transport = HttpTransport(settings.ground_health_url, settings.ground_device_key)
    else: transport = UdpTransport(settings.udp_host, settings.udp_port)
    try:
        while True:
            try: monitor.poll(timeout=1)
            except Exception as exc: log.warning("MAVLink receive unavailable: %s", exc); monitor.close()
            try:
                payload = collector.payload(settings.aircraft_id, monitor.status(), settings.camera_source)
                payload["watchdog"] = watchdog.snapshot()
                transport.send(payload); watchdog.success()
            except Exception as exc: watchdog.failure(); log.warning("health forward failed: %s failures=%s", exc, watchdog.snapshot()["consecutive_failures"])
            time.sleep(settings.health_interval_seconds)
    except KeyboardInterrupt: return 0
    finally: monitor.close()

if __name__ == "__main__": raise SystemExit(main())
