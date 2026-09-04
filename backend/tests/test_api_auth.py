"""Regression coverage for the same config object used by the running API."""
import sys
from pathlib import Path

import bcrypt
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def configured(monkeypatch, tmp_path):
    """Change environment values, then reload config exactly as a new process reads it."""
    import config

    def apply(*, protect_monitoring_routes: bool):
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("PROTECT_MONITORING_ROUTES", str(protect_monitoring_routes).lower())
        monkeypatch.setenv("JWT_SECRET", "test-secret-must-be-at-least-thirty-two-bytes")
        monkeypatch.setenv("ADMIN_USERNAME", "admin")
        monkeypatch.setenv("ADMIN_PASSWORD_HASH", bcrypt.hashpw(b"password", bcrypt.gensalt()).decode())
        monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
        monkeypatch.setenv("CAPTURE_DIRECTORY", str(tmp_path / "outputs"))
        settings = config.reload_settings()
        Path(settings.capture_directory).mkdir()
        return settings

    yield apply
    monkeypatch.undo()
    config.reload_settings()


@pytest.fixture
def client(monkeypatch):
    import api
    from fastapi.testclient import TestClient

    monkeypatch.setattr(api.worker, "start", lambda: None)
    monkeypatch.setattr(api.worker, "stop", lambda: None)
    monkeypatch.setattr(api, "generate_frames", lambda: iter([b"--frame\r\n\r\ntest\r\n"]))
    def make_client():
        return TestClient(api.app)
    return make_client


def token(client):
    return client.post("/auth/login", json={"username": "admin", "password": "password"}).json()["access_token"]


def test_trusted_lan_monitoring_resources_are_public_but_mutations_are_not(configured, client):
    settings = configured(protect_monitoring_routes=False)
    (Path(settings.capture_directory) / "test.jpg").write_bytes(b"safe-image")
    with client() as test_client:
        for route in ("/status", "/images", "/incidents", "/video", "/outputs/test.jpg"):
            response = test_client.get(route)
            assert response.status_code == 200, route
        assert test_client.get("/video").headers["content-type"].startswith("multipart/x-mixed-replace")

        payload = {"name": "Test", "points": [[0, 0], [1, 0], [1, 1]]}
        assert test_client.put("/zones", json=payload).status_code in (401, 403)
        assert test_client.delete("/zones/1").status_code in (401, 403)
        assert test_client.put("/rules/loitering", json={"enabled": True}).status_code in (401, 403)


def test_protected_monitoring_requires_auth_for_video_and_outputs(configured, client):
    settings = configured(protect_monitoring_routes=True)
    (Path(settings.capture_directory) / "test.jpg").write_bytes(b"safe-image")

    with client() as test_client:
        assert test_client.get("/video").status_code == 401
        assert test_client.get("/outputs/test.jpg").status_code == 401
        headers = {"Authorization": f"Bearer {token(test_client)}"}
        assert test_client.get("/video", headers=headers).status_code == 200
        assert test_client.get("/outputs/test.jpg", headers=headers).status_code == 200


def test_output_route_rejects_traversal(configured, client, tmp_path):
    configured(protect_monitoring_routes=False)
    secret = tmp_path / "secret.txt"
    secret.write_text("not an output", encoding="utf-8")

    with client() as test_client:
        response = test_client.get("/outputs/%2e%2e%2fsecret.txt")
        assert response.status_code in (404, 405)
        assert response.content != b"not an output"
