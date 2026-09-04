import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def test_telemetry_sampling_and_latest(monkeypatch, tmp_path):
    import telemetry
    calls=[]
    monkeypatch.setattr(telemetry.config, "settings", SimpleNamespace(database_path=str(tmp_path/"x.db"), airborne_telemetry_store_interval_seconds=60))
    monkeypatch.setattr(telemetry, "store_telemetry", lambda db, sample: calls.append(sample))
    telemetry._latest.clear(); telemetry._last_stored.clear()
    sample={"timestamp":1,"latitude":22.1,"longitude":73.1,"altitude_m":82,"ground_speed_mps":18,"heading_deg":140,"battery_percent":72}
    telemetry.ingest("AIR-01",sample); telemetry.ingest("AIR-01",sample)
    assert len(calls)==1 and telemetry.latest("AIR-01")["latitude"]==22.1

def test_airborne_telemetry_endpoint_auth_and_validation(monkeypatch):
    import api, config
    from fastapi.testclient import TestClient
    monkeypatch.setattr(api.worker,"start",lambda:None); monkeypatch.setattr(api.worker,"stop",lambda:None)
    base=config.settings
    monkeypatch.setattr(config,"settings",SimpleNamespace(**{**base.__dict__, "airborne_telemetry_enabled":True, "airborne_telemetry_api_key":"device-key", "camera_id":"AIR-01", "camera_mode":"airborne", "airborne_telemetry_store_interval_seconds":2}))
    payload={"timestamp":1720000000,"latitude":22.1,"longitude":73.1,"altitude_m":82,"ground_speed_mps":18,"heading_deg":140,"battery_percent":72}
    with TestClient(api.app) as client:
        assert client.post("/telemetry/aircraft/AIR-01",json=payload).status_code==401
        assert client.post("/telemetry/aircraft/AIR-01",headers={"X-Telemetry-Key":"device-key"},json=payload).status_code==200
        payload["latitude"]=91
        assert client.post("/telemetry/aircraft/AIR-01",headers={"X-Telemetry-Key":"device-key"},json=payload).status_code==422

def test_airborne_incident_persists_telemetry(tmp_path):
    from storage import init_db, create_incident, list_incidents
    db=str(tmp_path/"air.db"); init_db(db)
    create_incident(db,type="manual_capture",severity="low",message="capture",camera="AIR-01",telemetry={"latitude":22.3,"longitude":73.1,"altitude_m":91})
    assert list_incidents(db)[0]["telemetry"]["altitude_m"]==91
