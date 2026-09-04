from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class MissionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    source_type: Literal["live", "recorded"]
    camera_id: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=4000)


class MissionOut(BaseModel):
    id: str
    name: str
    source_type: Literal["live", "recorded"]
    camera_id: str | None
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    status: Literal["planned", "active", "completed", "aborted"]
    notes: str | None
    original_video_sha256: str | None = None
    duration_seconds: float | None = None
    fps: float | None = None
    width: int | None = None
    height: int | None = None
    frame_count: int | None = None
    processing_status: str | None = None


class MissionEventOut(BaseModel):
    id: str
    mission_id: str
    timestamp: datetime
    event_type: str
    severity: str
    camera_id: str | None
    incident_id: int | None
    evidence_id: str | None
    analysis_id: str | None
    metadata: dict[str, Any]


class MissionEvidenceOut(BaseModel):
    id: str
    mission_id: str | None
    camera_id: str | None
    created_at: datetime
    capture_timestamp: datetime
    source_type: str
    sha256: str
    incident_id: int | None
    analysis_id: str | None
    latitude: float | None
    longitude: float | None
    altitude_m: float | None
    heading_deg: float | None
    telemetry_associated: bool
    original_available: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractFrameRequest(BaseModel):
    timestamp_seconds: float
