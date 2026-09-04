import sys
from pathlib import Path
from types import SimpleNamespace

import bcrypt
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_structured_report_uses_only_persisted_data(monkeypatch, tmp_path):
    import api, config
    from airborne import evidence, events, service
    from storage import init_db, store_telemetry
    base = dict(config.settings.__dict__)
    monkeypatch.setattr(config, "settings", SimpleNamespace(**{**base, "database_path": str(tmp_path / "report.db"), "capture_directory": str(tmp_path / "outputs"), "auth_enabled": False, "admin_username": "admin", "admin_password_hash": bcrypt.hashpw(b"password", bcrypt.gensalt()).decode()}))
    monkeypatch.setattr(api.worker, "start", lambda: None); monkeypatch.setattr(api.worker, "stop", lambda: None)
    with TestClient(api.app) as client:
        mission = service.create_mission(name="Flight", source_type="live", camera_id="AIR-01")
        service.transition_mission(mission["id"], "active")
        item = evidence.create_bytes(data=b"evidence", filename="frame.jpg", source_type="manual_capture", mission_id=mission["id"], latitude=22.3, longitude=73.1, altitude_m=100)
        events.create(mission["id"], "video_lost")
        events.create(mission["id"], "video_restored")
        store_telemetry(config.settings.database_path, {"camera_id":"AIR-01", "timestamp":100, "latitude":22.3, "longitude":73.1, "altitude_m":100, "mission_id":mission["id"]})
        report = client.get(f"/airborne/missions/{mission['id']}/report")
        assert report.status_code == 200
        body = report.json()
        assert body["report_version"] == "1.0" and body["summary"]["evidence_count"] == 1
        assert body["track"] == [{"timestamp": 100, "latitude": 22.3, "longitude": 73.1, "altitude_m": 100.0}]
        assert body["evidence"][0]["id"] == item["id"] and body["analyses"] == []
