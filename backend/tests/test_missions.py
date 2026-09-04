"""Phase 1 airborne mission-domain coverage; no camera, network, or GPU required."""
import hashlib
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import bcrypt
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def mission_client(monkeypatch, tmp_path):
    import api
    import config
    from fastapi.testclient import TestClient
    base_values = dict(config.settings.__dict__)

    def make(*, auth_enabled=False, protect_monitoring_routes=False):
        monkeypatch.setattr(config, "settings", SimpleNamespace(**{
            **base_values, "database_path": str(tmp_path / "missions.db"),
            "capture_directory": str(tmp_path / "outputs"), "auth_enabled": auth_enabled,
            "protect_monitoring_routes": protect_monitoring_routes,
            "jwt_secret": "test-secret-must-be-at-least-thirty-two-bytes",
            "admin_username": "admin",
            "admin_password_hash": bcrypt.hashpw(b"password", bcrypt.gensalt()).decode(),
        }))
        monkeypatch.setattr(api.worker, "start", lambda: None)
        monkeypatch.setattr(api.worker, "stop", lambda: None)
        return TestClient(api.app)
    return make


def create(client, **extra):
    response = client.post("/airborne/missions", json={"name": "Survey", "source_type": "live", "camera_id": "AIR-01", **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_mission_create_list_and_get(mission_client):
    with mission_client() as client:
        created = create(client, notes="ridge pass")
        assert created["status"] == "planned" and created["id"]
        assert client.get("/airborne/missions").json()[0]["id"] == created["id"]
        assert client.get(f"/airborne/missions/{created['id']}").json()["notes"] == "ridge pass"


def test_start_complete_and_event_persistence(mission_client):
    with mission_client() as client:
        mission = create(client)
        assert client.post(f"/airborne/missions/{mission['id']}/start").json()["status"] == "active"
        done = client.post(f"/airborne/missions/{mission['id']}/complete")
        assert done.status_code == 200 and done.json()["ended_at"]
        events = client.get(f"/airborne/missions/{mission['id']}/events").json()
        assert [event["event_type"] for event in events] == ["mission_completed", "mission_started"]


def test_abort_and_invalid_state_transition(mission_client):
    with mission_client() as client:
        mission = create(client)
        assert client.post(f"/airborne/missions/{mission['id']}/complete").status_code == 409
        client.post(f"/airborne/missions/{mission['id']}/start")
        assert client.post(f"/airborne/missions/{mission['id']}/abort").json()["status"] == "aborted"
        assert client.post(f"/airborne/missions/{mission['id']}/complete").status_code == 409


def test_only_one_active_live_mission_per_camera(mission_client):
    with mission_client() as client:
        one, two = create(client), create(client)
        assert client.post(f"/airborne/missions/{one['id']}/start").status_code == 200
        assert client.post(f"/airborne/missions/{two['id']}/start").status_code == 409


def test_evidence_persistence_hash_and_safe_response(mission_client):
    with mission_client() as client:
        mission = create(client)
        from airborne.evidence import create_bytes
        payload = b"immutable mission evidence"
        evidence = create_bytes(data=payload, filename="capture.jpg", source_type="manual_capture", mission_id=mission["id"], camera_id="AIR-01")
        assert evidence["sha256"] == hashlib.sha256(payload).hexdigest()
        assert "original_path" not in evidence and evidence["original_available"] is True
        listed = client.get(f"/airborne/missions/{mission['id']}/evidence").json()
        assert listed[0]["id"] == evidence["id"] and "original_path" not in listed[0]
        original = client.get(f"/airborne/evidence/{evidence['id']}/original")
        assert original.status_code == 200 and original.content == payload
        assert any(item["event_type"] == "evidence_created" for item in client.get(f"/airborne/missions/{mission['id']}/events").json())


def test_mission_mutations_require_auth_but_reads_follow_monitoring_policy(mission_client):
    with mission_client(auth_enabled=True, protect_monitoring_routes=False) as client:
        assert client.post("/airborne/missions", json={"name": "Secure", "source_type": "live"}).status_code == 401
        assert client.get("/airborne/missions").status_code == 200
        token = client.post("/auth/login", json={"username": "admin", "password": "password"}).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert client.post("/airborne/missions", headers=headers, json={"name": "Secure", "source_type": "live"}).status_code == 201
    with mission_client(auth_enabled=True, protect_monitoring_routes=True) as client:
        assert client.get("/airborne/missions").status_code == 401


def test_existing_database_migration_adds_mission_tables(tmp_path):
    from storage import init_db
    db = str(tmp_path / "legacy.db")
    init_db(db)
    # A database initialized by an older running instance can be reopened
    # idempotently after this additive migration is deployed.
    init_db(db)
    conn = sqlite3.connect(db)
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    conn.close()
    assert {"missions", "mission_events", "mission_evidence"} <= names
    assert {"idx_missions_status", "idx_missions_created_at", "idx_mission_events_mission_time", "idx_mission_evidence_mission", "idx_mission_evidence_created_at"} <= indexes
