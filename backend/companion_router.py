"""Small, credential-gated receiver for companion health metadata only."""
from __future__ import annotations
import hmac
from typing import Any
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
import config

router = APIRouter(prefix="/companion", tags=["Companion Health"])
_latest: dict[str, dict[str, Any]] = {}

class PiHealth(BaseModel):
    online: bool; cpu_percent: float | None = Field(default=None, ge=0, le=100); memory_percent: float | None = Field(default=None, ge=0, le=100)
    temperature_c: float | None = None; disk_free_mb: float | None = Field(default=None, ge=0)
class CameraHealth(BaseModel): reachable: bool | None = None
class MavlinkHealth(BaseModel): connected: bool; heartbeat_age_seconds: float | None = Field(default=None, ge=0); system_id: int | None = None; component_id: int | None = None
class CompanionHealth(BaseModel):
    aircraft_id: str = Field(min_length=1, max_length=64); timestamp: str; pi: PiHealth; camera: CameraHealth; mavlink: MavlinkHealth

def _authorized(key: str | None) -> None:
    expected = config.settings.companion_health_api_key
    if not config.settings.companion_health_enabled or not expected or not key or not hmac.compare_digest(key, expected):
        raise HTTPException(401, "Invalid companion credentials")

@router.post("/health/{aircraft_id}")
def receive_health(aircraft_id: str, payload: CompanionHealth, x_companion_key: str | None = Header(default=None)):
    _authorized(x_companion_key)
    if payload.aircraft_id != aircraft_id: raise HTTPException(422, "aircraft_id does not match route")
    _latest[aircraft_id] = payload.model_dump()
    return {"accepted": True}

@router.get("/health/{aircraft_id}")
def latest_health(aircraft_id: str):
    # This endpoint intentionally returns only metadata; route protection follows the app's monitoring policy at deployment.
    return {"health": _latest.get(aircraft_id)}
