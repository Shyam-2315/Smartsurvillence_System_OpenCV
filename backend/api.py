import os
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import threading

from stream import generate_frames
import worker

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


app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")