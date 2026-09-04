import sys
from pathlib import Path
from types import SimpleNamespace

import bcrypt
import numpy as np
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_live_capture_associates_fresh_telemetry_and_investigates(monkeypatch, tmp_path):
    import api, config, telemetry, worker
    from visual_intelligence import service as visual_service
    base = dict(config.settings.__dict__)
    monkeypatch.setattr(config, "settings", SimpleNamespace(**{
        **base, "database_path": str(tmp_path / "live.db"), "capture_directory": str(tmp_path / "outputs"),
        "airborne_camera_id": "AIR-01", "airborne_telemetry_association_max_seconds": 3,
        "auth_enabled": False, "admin_username": "admin", "admin_password_hash": bcrypt.hashpw(b"password", bcrypt.gensalt()).decode(),
    }))
    monkeypatch.setattr(api.worker, "start", lambda: None); monkeypatch.setattr(api.worker, "stop", lambda: None)
    monkeypatch.setattr(worker, "processed_frame_snapshot", lambda: np.zeros((24, 32, 3), dtype=np.uint8))
    monkeypatch.setattr(visual_service, "ROOT", Path(config.settings.capture_directory).resolve() / "visual_intelligence")
    monkeypatch.setattr(visual_service, "analyze", lambda analysis_id: visual_service.get(analysis_id))
    telemetry._latest.clear(); telemetry._last_stored.clear(); telemetry._history.clear()
    with TestClient(api.app) as client:
        mission = client.post("/airborne/missions", json={"name": "Live", "source_type": "live", "camera_id": "AIR-01"}).json()
        client.post(f"/airborne/missions/{mission['id']}/start")
        telemetry.ingest("AIR-01", {"timestamp": 123, "latitude": 22.3, "longitude": 73.1, "altitude_m": 120, "heading_deg": 90, "ground_speed_mps": 18})
        captured = client.post("/airborne/live/capture")
        assert captured.status_code == 201, captured.text
        payload = captured.json(); evidence = payload["evidence"]
        assert evidence["mission_id"] == mission["id"] and evidence["telemetry_associated"] is True
        assert evidence["latitude"] == 22.3 and evidence["metadata"]["ground_speed_mps"] == 18
        analysis = client.post(f"/airborne/evidence/{evidence['id']}/investigate")
        assert analysis.status_code == 201 and analysis.json()["source_type"] == "airborne_live_capture"
        assert analysis.json()["metadata"]["source_context"]["telemetry"]["latitude"] == 22.3
        events = client.get(f"/airborne/missions/{mission['id']}/events").json()
        assert any(event["event_type"] == "manual_capture" and event["analysis_id"] == analysis.json()["id"] for event in events)


def test_phase11_capture_alias_creates_immutable_airborne_evidence(monkeypatch, tmp_path):
    import api, config, worker
    base = dict(config.settings.__dict__)
    monkeypatch.setattr(config, "settings", SimpleNamespace(**{**base, "database_path": str(tmp_path / "capture.db"), "capture_directory": str(tmp_path / "outputs"), "airborne_camera_id": "AIR-01", "auth_enabled": False}))
    monkeypatch.setattr(api.worker, "start", lambda: None); monkeypatch.setattr(api.worker, "stop", lambda: None)
    monkeypatch.setattr(worker, "processed_frame_snapshot", lambda: np.zeros((8, 8, 3), dtype=np.uint8))
    with TestClient(api.app) as client:
        result = client.post("/airborne/capture")
        assert result.status_code == 201
        evidence = result.json()["evidence"]
        assert evidence["camera_id"] == "AIR-01" and len(evidence["sha256"]) == 64 and evidence["original_available"] is True


def test_live_capture_never_uses_stale_coordinates(monkeypatch, tmp_path):
    import api, config, telemetry, worker
    base = dict(config.settings.__dict__)
    monkeypatch.setattr(config, "settings", SimpleNamespace(**{**base, "database_path": str(tmp_path / "stale.db"), "capture_directory": str(tmp_path / "outputs"), "airborne_camera_id": "AIR-01", "airborne_telemetry_association_max_seconds": .1, "auth_enabled": False}))
    monkeypatch.setattr(api.worker, "start", lambda: None); monkeypatch.setattr(api.worker, "stop", lambda: None)
    monkeypatch.setattr(worker, "processed_frame_snapshot", lambda: np.zeros((24, 32, 3), dtype=np.uint8))
    telemetry._latest.clear(); telemetry._last_stored.clear(); telemetry._history.clear()
    with TestClient(api.app) as client:
        telemetry.ingest("AIR-01", {"timestamp": 1, "latitude": 22.3, "longitude": 73.1})
        import time; time.sleep(.12)
        result = client.post("/airborne/live/capture").json()["evidence"]
        assert result["telemetry_associated"] is False and result["latitude"] is None
