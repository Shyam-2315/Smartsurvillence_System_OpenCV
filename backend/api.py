import os
from datetime import datetime

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import threading
from pydantic import BaseModel, Field

from stream import generate_frames
import worker
from storage import DEFAULT_DB_PATH, init_db, list_incidents, list_zones, upsert_zone, delete_zone, get_rule, set_rule

app = FastAPI()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "outputs"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    init_db(DEFAULT_DB_PATH)

    threading.Thread(
        target=worker.camera_worker,
        daemon=True
    ).start()

    threading.Thread(
        target=worker.ai_worker,
        daemon=True
    ).start()

    print("✅ Workers Started")


@app.get("/")
def home():
    return {
        "message": "Smart Surveillance Running"
    }


@app.get("/video")
def video_feed():

    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/alerts")
def get_alerts():
    # Dashboard endpoint: latest alert state and recent history.
    return {
        "active_alerts": [
            {"track_id": int(track_id), "duration_sec": round(float(duration), 2)}
            for track_id, duration in worker.latest_alerts
        ],
        "history": worker.alert_history[-20:],
    }


@app.get("/images")
def get_images():
    if not os.path.exists(OUTPUTS_DIR):
        return []

    files = []
    for filename in os.listdir(OUTPUTS_DIR):
        if not filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            continue
        full_path = os.path.join(OUTPUTS_DIR, filename)
        ts = datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat()
        files.append(
            {
                "filename": filename,
                "timestamp": ts,
                "type": "Loitering",
            }
        )

    files.sort(key=lambda item: item["timestamp"], reverse=True)
    return files[:200]


@app.get("/status")
def get_status():
    return worker.latest_status


class Incident(BaseModel):
    id: int
    created_at_ts: int
    type: str
    severity: str
    message: str | None = None
    camera: str | None = None
    zone_id: int | None = None
    track_id: int | None = None
    duration_sec: float | None = None
    screenshot_filename: str | None = None


@app.get("/incidents", response_model=list[Incident])
def incidents(limit: int = 50, offset: int = 0, type: str | None = None, severity: str | None = None, since_ts: int | None = None):
    return list_incidents(DEFAULT_DB_PATH, limit=limit, offset=offset, type=type, severity=severity, since_ts=since_ts)


class ZoneIn(BaseModel):
    id: int | None = None
    name: str = Field(min_length=1, max_length=64)
    points: list[list[float]] = Field(min_length=3)


@app.get("/zones")
def zones():
    return list_zones(DEFAULT_DB_PATH)


@app.put("/zones")
def put_zone(zone: ZoneIn):
    # basic validation of normalized points
    pts = []
    for p in zone.points:
        if not isinstance(p, list) or len(p) != 2:
            raise HTTPException(status_code=400, detail="Each point must be [x,y]")
        x, y = float(p[0]), float(p[1])
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            raise HTTPException(status_code=400, detail="Points must be normalized (0..1)")
        pts.append([x, y])
    return upsert_zone(DEFAULT_DB_PATH, zone.id, zone.name, pts)


@app.delete("/zones/{zone_id}")
def del_zone(zone_id: int):
    delete_zone(DEFAULT_DB_PATH, int(zone_id))
    return {"ok": True}


class LoiterRule(BaseModel):
    enabled: bool = True
    min_duration_sec: float = Field(default=10, ge=1, le=600)
    zone_id: int | None = None
    cooldown_sec: float = Field(default=30, ge=0, le=3600)


@app.get("/rules/loitering")
def get_loitering_rule():
    rule = get_rule(DEFAULT_DB_PATH, "loitering")
    if not rule:
        return LoiterRule().model_dump()
    return rule


@app.put("/rules/loitering")
def set_loitering_rule(rule: LoiterRule):
    return set_rule(DEFAULT_DB_PATH, "loitering", rule.model_dump())


app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")