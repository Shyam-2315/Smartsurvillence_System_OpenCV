from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(value: str | None, default: bool = False) -> bool:
    return (value or str(default)).lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class CompanionSettings:
    aircraft_id: str = "AIR-01"
    mavlink_connection: str = "/dev/serial0"
    mavlink_baud: int = 57600
    mavlink_read_only: bool = True
    health_interval_seconds: float = 5.0
    camera_source: str | None = None
    transport: str = "udp"
    udp_host: str = "127.0.0.1"
    udp_port: int = 14600
    ground_health_url: str | None = None
    ground_device_key: str | None = None
    log_file: str = "/var/log/vayu-companion/companion.log"
    log_max_bytes: int = 2_000_000
    log_backups: int = 3

    @classmethod
    def from_env(cls) -> "CompanionSettings":
        transport = os.getenv("COMPANION_TRANSPORT", "udp").strip().lower()
        if transport not in {"udp", "http"}: raise ValueError("COMPANION_TRANSPORT must be udp or http")
        read_only = _bool(os.getenv("COMPANION_MAVLINK_READ_ONLY"), True)
        if not read_only: raise ValueError("COMPANION_MAVLINK_READ_ONLY must remain true")
        return cls(
            aircraft_id=os.getenv("COMPANION_AIRCRAFT_ID", "AIR-01").strip()[:64],
            mavlink_connection=os.getenv("COMPANION_MAVLINK_CONNECTION", "/dev/serial0").strip(),
            mavlink_baud=max(1200, min(921600, int(os.getenv("COMPANION_MAVLINK_BAUD", "57600")))),
            mavlink_read_only=read_only, health_interval_seconds=max(1, min(300, float(os.getenv("COMPANION_HEALTH_INTERVAL_SECONDS", "5")))),
            camera_source=os.getenv("COMPANION_CAMERA_SOURCE") or None, transport=transport,
            udp_host=os.getenv("COMPANION_UDP_HOST", "127.0.0.1").strip(), udp_port=int(os.getenv("COMPANION_UDP_PORT", "14600")),
            ground_health_url=os.getenv("COMPANION_GROUND_HEALTH_URL") or None, ground_device_key=os.getenv("COMPANION_GROUND_DEVICE_KEY") or None,
            log_file=os.getenv("COMPANION_LOG_FILE", "/var/log/vayu-companion/companion.log"),
            log_max_bytes=max(1024, int(os.getenv("COMPANION_LOG_MAX_BYTES", "2000000"))), log_backups=max(1, min(20, int(os.getenv("COMPANION_LOG_BACKUPS", "3"))),),
        )
