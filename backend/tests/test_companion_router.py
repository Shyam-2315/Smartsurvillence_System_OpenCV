import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def test_companion_health_requires_dedicated_key(monkeypatch):
    import api, config
    from fastapi.testclient import TestClient
    monkeypatch.setattr(config, "settings", SimpleNamespace(**{**config.settings.__dict__, "companion_health_enabled": True, "companion_health_api_key": "pi-key", "auth_enabled": False}))
    monkeypatch.setattr(api.worker, "start", lambda: None); monkeypatch.setattr(api.worker, "stop", lambda: None)
    payload = {"aircraft_id":"AIR-01","timestamp":"2026-01-01T00:00:00Z","pi":{"online":True,"cpu_percent":1,"memory_percent":2,"temperature_c":None,"disk_free_mb":1},"camera":{"reachable":None},"mavlink":{"connected":True,"heartbeat_age_seconds":1,"system_id":1,"component_id":1}}
    with TestClient(api.app) as client:
        assert client.post("/companion/health/AIR-01", json=payload).status_code == 401
        assert client.post("/companion/health/AIR-01", json=payload, headers={"X-Companion-Key":"pi-key"}).json()["accepted"] is True
