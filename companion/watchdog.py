from __future__ import annotations
import time

class WatchdogState:
    """Reports loop health for systemd/external supervision; it never reboots the Pi."""
    def __init__(self) -> None: self.last_success_at: float | None = None; self.consecutive_failures = 0
    def success(self) -> None: self.last_success_at = time.time(); self.consecutive_failures = 0
    def failure(self) -> None: self.consecutive_failures += 1
    def snapshot(self) -> dict[str, float | int | None]:
        age = None if self.last_success_at is None else round(max(0, time.time() - self.last_success_at), 2)
        return {"last_success_age_seconds": age, "consecutive_failures": self.consecutive_failures}
