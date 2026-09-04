"""Phase 2 recorded-mission upload coverage; generated videos require no network or GPU."""
import hashlib
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import bcrypt
import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def video_bytes(tmp_path: Path) -> bytes:
    path = tmp_path / "source.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (32, 24))
    assert writer.isOpened()
    for _ in range(5): writer.write(np.zeros((24, 32, 3), dtype=np.uint8))
    writer.release()
    return path.read_bytes()


@pytest.fixture
def client_factory(monkeypatch, tmp_path):
    import api, config
    from fastapi.testclient import TestClient
    base = dict(config.settings.__dict__)
    def make(auth=False, limit=2):
        monkeypatch.setattr(config, "settings", SimpleNamespace(**{**base, "database_path": str(tmp_path / "missions.db"), "recorded_mission_storage": str(tmp_path / "mission-storage"), "recorded_mission_max_upload_mb": limit, "auth_enabled": auth, "jwt_secret": "test-secret-must-be-at-least-thirty-two-bytes", "admin_username": "admin", "admin_password_hash": bcrypt.hashpw(b"password", bcrypt.gensalt()).decode()}))
        monkeypatch.setattr(api.worker, "start", lambda: None); monkeypatch.setattr(api.worker, "stop", lambda: None)
        return TestClient(api.app)
    return make


def upload(client, data, filename="flight.mp4", headers=None):
    return client.post("/airborne/missions/recorded", data={"name": "Flight", "notes": "test run"}, files={"video": (filename, data, "video/mp4")}, headers=headers or {})


def test_valid_video_metadata_hash_immutable_and_serving(client_factory, tmp_path):
    payload = video_bytes(tmp_path)
    with client_factory() as client:
        response = upload(client, payload); assert response.status_code == 201, response.text
        mission = response.json()
        assert mission["source_type"] == "recorded" and mission["processing_status"] == "ready"
        assert mission["original_video_sha256"] == hashlib.sha256(payload).hexdigest()
        assert (mission["width"], mission["height"], mission["frame_count"]) == (32, 24, 5)
        assert mission["fps"] == pytest.approx(10) and mission["duration_seconds"] == pytest.approx(.5)
        assert "original_video_path" not in mission
        assert client.get(f"/airborne/missions/recorded/{mission['id']}").status_code == 200
        served = client.get(f"/airborne/missions/{mission['id']}/video"); assert served.status_code == 200 and served.content == payload
        import config
        original = next((Path(config.settings.recorded_mission_storage) / "originals").iterdir())
        assert original.name != "flight.mp4" and not (original.stat().st_mode & 0o200)


@pytest.mark.parametrize("filename,payload,status", [("bad.txt", b"x", 415), ("fake.mp4", b"not a video", 422), ("broken.mkv", b"\x00" * 20, 422)])
def test_rejects_unsupported_invalid_and_corrupt_videos(client_factory, tmp_path, filename, payload, status):
    with client_factory() as client: assert upload(client, payload, filename).status_code == status


def test_rejects_oversized_stream_and_leaves_no_original(client_factory, tmp_path):
    with client_factory(limit=1) as client:
        assert upload(client, b"x" * (1024 * 1024 + 1)).status_code == 413
        import config
        originals = Path(config.settings.recorded_mission_storage) / "originals"
        assert not list(originals.glob("*"))


def test_authentication_and_safe_path_rejection(client_factory, tmp_path):
    payload = video_bytes(tmp_path)
    with client_factory(auth=True) as client:
        assert upload(client, payload).status_code == 401
        token = client.post("/auth/login", json={"username": "admin", "password": "password"}).json()["access_token"]
        mission = upload(client, payload, headers={"Authorization": f"Bearer {token}"}).json()
        import config
        conn = sqlite3.connect(config.settings.database_path)
        conn.execute("UPDATE missions SET original_video_path=? WHERE id=?", ("../outside.mp4", mission["id"])); conn.commit(); conn.close()
        assert client.get(f"/airborne/missions/{mission['id']}/video").status_code == 404
