"""Recorded mission evidence can enter Visual Intelligence only by analyst request."""
import hashlib
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import bcrypt
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def video_bytes(tmp_path: Path) -> bytes:
    path = tmp_path / "recorded.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 4, (32, 24))
    for index in range(8):
        writer.write(np.full((24, 32, 3), index * 20, dtype=np.uint8))
    writer.release()
    return path.read_bytes()


@pytest.fixture
def client(monkeypatch, tmp_path):
    import api
    import config
    from visual_intelligence import service as visual_service

    base = dict(config.settings.__dict__)
    monkeypatch.setattr(config, "settings", SimpleNamespace(**{
        **base, "database_path": str(tmp_path / "phase5.db"), "capture_directory": str(tmp_path / "outputs"),
        "recorded_mission_storage": str(tmp_path / "missions"), "auth_enabled": False,
        "admin_username": "admin", "admin_password_hash": bcrypt.hashpw(b"password", bcrypt.gensalt()).decode(),
        "jwt_secret": "test-secret-must-be-at-least-thirty-two-bytes",
    }))
    monkeypatch.setattr(api.worker, "start", lambda: None)
    monkeypatch.setattr(api.worker, "stop", lambda: None)
    monkeypatch.setattr(visual_service, "ROOT", Path(config.settings.capture_directory).resolve() / "visual_intelligence")
    monkeypatch.setattr(visual_service, "analyze", lambda analysis_id: visual_service.get(analysis_id))
    return TestClient(api.app)


def upload(client, data):
    response = client.post("/airborne/missions/recorded", data={"name": "Recorded flight"}, files={"video": ("flight.mp4", data, "video/mp4")})
    assert response.status_code == 201, response.text
    return response.json()


def test_extract_immutable_frame_and_visual_linkage(client, tmp_path):
    with client as app:
        mission = upload(app, video_bytes(tmp_path))
        assert app.post(f"/airborne/missions/{mission['id']}/extract-frame", json={"timestamp_seconds": -1}).status_code == 422
        assert app.post(f"/airborne/missions/{mission['id']}/extract-frame", json={"timestamp_seconds": mission["duration_seconds"]}).status_code == 422
        extracted = app.post(f"/airborne/missions/{mission['id']}/extract-frame", json={"timestamp_seconds": 0.5})
        assert extracted.status_code == 201, extracted.text
        payload = extracted.json(); evidence = payload["evidence"]; event = payload["event"]
        original = app.get(f"/airborne/evidence/{evidence['id']}/original")
        assert original.status_code == 200 and evidence["sha256"] == hashlib.sha256(original.content).hexdigest()
        analysis = app.post(f"/airborne/missions/{mission['id']}/evidence/{evidence['id']}/investigate")
        assert analysis.status_code == 201, analysis.text
        record = analysis.json()
        assert record["source_type"] == "recorded_mission"
        assert (record["mission_id"], record["mission_event_id"], record["evidence_id"]) == (mission["id"], event["id"], evidence["id"])
        assert record["video_timestamp_seconds"] == pytest.approx(0.5)
        assert record["metadata"]["source_context"]["mission_id"] == mission["id"]
        assert app.post(f"/airborne/missions/{mission['id']}/evidence/{evidence['id']}/investigate").json()["id"] == record["id"]
        import config
        conn = sqlite3.connect(config.settings.database_path)
        assert conn.execute("SELECT analysis_id FROM mission_evidence WHERE id=?", (evidence["id"],)).fetchone()[0] == record["id"]
        assert conn.execute("SELECT analysis_id FROM mission_events WHERE id=?", (event["id"],)).fetchone()[0] == record["id"]
        conn.close()


def test_extract_and_investigate_require_admin(client, tmp_path, monkeypatch):
    import config
    with client as app:
        mission = upload(app, video_bytes(tmp_path))
        monkeypatch.setattr(config.settings, "auth_enabled", True)
        assert app.post(f"/airborne/missions/{mission['id']}/extract-frame", json={"timestamp_seconds": 0.1}).status_code == 401
        token = app.post("/auth/login", json={"username": "admin", "password": "password"}).json()["access_token"]
        extracted = app.post(f"/airborne/missions/{mission['id']}/extract-frame", headers={"Authorization": f"Bearer {token}"}, json={"timestamp_seconds": 0.1})
        assert extracted.status_code == 201
        app.cookies.clear()
        assert app.post(f"/airborne/missions/{mission['id']}/evidence/{extracted.json()['evidence']['id']}/investigate").status_code == 401
