"""MAVLink normalization and lifecycle tests use synthetic messages only."""
import sqlite3
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class Message:
    def __init__(self, kind, **values):
        self.kind = kind
        self.__dict__.update(values)
    def get_type(self): return self.kind
    def get_srcSystem(self): return getattr(self, "system_id", None)
    def get_srcComponent(self): return getattr(self, "component_id", None)


def settings(tmp_path=None, **overrides):
    values = {
        "mavlink_enabled": True, "mavlink_read_only": True, "mavlink_connection": "udpin:127.0.0.1:14551",
        "mavlink_simulation_mode": True, "mavlink_heartbeat_timeout_seconds": 5, "mavlink_reconnect_seconds": .1, "mavlink_disconnect_seconds": 15,
        "airborne_telemetry_stale_seconds": 5, "airborne_telemetry_store_interval_seconds": 2,
        "airborne_telemetry_association_max_seconds": 3, "airborne_camera_id": "AIR-01",
        "database_path": str(tmp_path / "mavlink.db") if tmp_path else "unused.db",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_normalizes_heartbeat_position_gps_hud_battery_and_attitude(monkeypatch, tmp_path):
    import mavlink_service
    monkeypatch.setattr(mavlink_service.config, "settings", settings(tmp_path))
    published = []
    monkeypatch.setattr(mavlink_service, "ingest", lambda camera, sample: published.append((camera, sample)))
    service = mavlink_service.MavlinkTelemetryService()
    service.handle_message(Message("HEARTBEAT", base_mode=128), now=100)
    service.handle_message(Message("GLOBAL_POSITION_INT", lat=223000000, lon=731000000, alt=121500, relative_alt=21500, hdg=9200), now=101)
    service.handle_message(Message("GPS_RAW_INT", fix_type=3, satellites_visible=12, lat=223000100, lon=731000100, alt=121600), now=102)
    service.handle_message(Message("VFR_HUD", groundspeed=18.5, airspeed=20.1, heading=93), now=103)
    service.handle_message(Message("SYS_STATUS", battery_remaining=77, voltage_battery=12000, current_battery=345), now=104)
    service.handle_message(Message("ATTITUDE", roll=0.1, pitch=-0.2, yaw=1.0), now=105)
    sample = published[-1][1]
    assert published[-1][0] == "AIR-01"
    assert sample["latitude"] == 22.30001 and sample["longitude"] == 73.10001
    assert sample["altitude_m"] == 121.6 and sample["relative_altitude_m"] == 21.5
    assert sample["ground_speed_mps"] == 18.5 and sample["air_speed_mps"] == 20.1
    assert sample["heading_deg"] == 93 and sample["battery_percent"] == 77
    assert sample["battery_voltage_v"] == 12 and sample["battery_current_a"] == 3.45
    assert sample["source"] == "sitl" and sample["received_at"] == 105
    assert sample["armed"] is True and sample["gps_fix"] == 3 and sample["satellite_count"] == 12
    assert round(sample["roll_deg"], 1) == 5.7 and round(sample["pitch_deg"], 1) == -11.5


def test_disabled_start_stale_state_and_connection_loss(monkeypatch, tmp_path):
    import mavlink_service
    service = mavlink_service.MavlinkTelemetryService()
    monkeypatch.setattr(mavlink_service.config, "settings", settings(tmp_path, mavlink_enabled=False))
    service.start(); assert service.status()["state"] == "DISABLED"
    monkeypatch.setattr(mavlink_service.config, "settings", settings(tmp_path, airborne_telemetry_stale_seconds=1, mavlink_heartbeat_timeout_seconds=1))
    monkeypatch.setattr(mavlink_service, "ingest", lambda *_: None)
    service.handle_message(Message("HEARTBEAT", base_mode=0), now=time.time() - 2)
    assert service.status()["state"] == "STALE"
    class BrokenConnection:
        def recv_match(self, **_): raise OSError("connection lost")
        def close(self): pass
    class FakeMavutil:
        @staticmethod
        def mavlink_connection(*_, **__): return BrokenConnection()
    monkeypatch.setattr(mavlink_service, "mavutil", FakeMavutil)
    service.start(); time.sleep(.05); service.stop()
    assert service.status()["state"] == "RECONNECTING"


def test_heartbeat_link_loss_becomes_stale_then_disconnected_and_restores(monkeypatch, tmp_path):
    import mavlink_service
    monkeypatch.setattr(mavlink_service.config, "settings", settings(tmp_path, mavlink_heartbeat_timeout_seconds=1, mavlink_disconnect_seconds=2))
    monkeypatch.setattr(mavlink_service, "ingest", lambda *_: None)
    service = mavlink_service.MavlinkTelemetryService()
    service.handle_message(Message("HEARTBEAT", base_mode=0), now=time.time() - 1.5)
    assert service.status()["state"] == "STALE"
    service.handle_message(Message("HEARTBEAT", base_mode=0), now=time.time() - 2.5)
    assert service.status()["state"] == "DISCONNECTED"
    service.handle_message(Message("HEARTBEAT", base_mode=0), now=time.time())
    assert service.status()["state"] == "CONNECTED"


def test_zero_coordinates_are_not_synthesized_and_status_exposes_simulation(monkeypatch, tmp_path):
    import mavlink_service
    monkeypatch.setattr(mavlink_service.config, "settings", settings(tmp_path))
    published = []
    monkeypatch.setattr(mavlink_service, "ingest", lambda _camera, sample: published.append(sample))
    service = mavlink_service.MavlinkTelemetryService()
    service.handle_message(Message("GLOBAL_POSITION_INT", lat=0, lon=0, alt=1000, relative_alt=500, hdg=65535), now=10)
    assert published[-1]["latitude"] is None and published[-1]["longitude"] is None
    assert published[-1]["heading_deg"] is None
    assert service.status()["simulation"] is True and service.status()["telemetry_source"] == "sitl"


def test_real_pixhawk_source_label_and_heartbeat_identifiers(monkeypatch, tmp_path):
    import mavlink_service
    monkeypatch.setattr(mavlink_service.config, "settings", settings(tmp_path, mavlink_simulation_mode=False, mavlink_connection="COM19"))
    published = []
    monkeypatch.setattr(mavlink_service, "ingest", lambda _camera, sample: published.append(sample))
    service = mavlink_service.MavlinkTelemetryService()
    service.handle_message(Message("HEARTBEAT", base_mode=128, system_id=1, component_id=1), now=50)
    assert service.status()["telemetry_source"] == "real" and service.status()["simulation"] is False
    assert published[-1]["source"] == "real" and published[-1]["system_id"] == 1 and published[-1]["component_id"] == 1
    assert published[-1]["armed"] is True


def test_serial_and_udp_connection_validation():
    from config import parse_mavlink_connection
    assert parse_mavlink_connection("com7") == "COM7"
    assert parse_mavlink_connection("udpin:127.0.0.1:14551") == "udpin:127.0.0.1:14551"
    try: parse_mavlink_connection("radio-auto")
    except ValueError: pass
    else: assert False, "an ambiguous MAVLink endpoint must be rejected"


def test_read_only_receiver_has_no_control_operations():
    import inspect
    import mavlink_service
    source = inspect.getsource(mavlink_service)
    for forbidden in ("command_long_send", "set_mode", "arducopter_arm", "mission_item_send", "param_set_send", "servo"):
        assert forbidden not in source


def test_persistence_interval_and_real_mission_track(monkeypatch, tmp_path):
    import config
    import telemetry
    from storage import init_db, list_mission_track
    from airborne import service as mission_service
    monkeypatch.setattr(config, "settings", SimpleNamespace(**{**config.settings.__dict__, **settings(tmp_path).__dict__, "camera_id": "AIR-01", "camera_mode": "airborne"}))
    init_db(config.settings.database_path)
    mission = mission_service.create_mission(name="Live flight", source_type="live", camera_id="AIR-01")
    mission_service.transition_mission(mission["id"], "active")
    telemetry._latest.clear(); telemetry._last_stored.clear()
    telemetry.ingest("AIR-01", {"timestamp": 100, "latitude": 22.3, "longitude": 73.1, "altitude_m": 120})
    telemetry.ingest("AIR-01", {"timestamp": 101, "latitude": 22.4, "longitude": 73.2, "altitude_m": 121})
    rows = list_mission_track(config.settings.database_path, mission["id"])
    assert len(rows) == 1 and rows[0]["latitude"] == 22.3 and rows[0]["altitude_m"] == 120
    conn = sqlite3.connect(config.settings.database_path)
    assert conn.execute("SELECT mission_id FROM aircraft_telemetry").fetchone()[0] == mission["id"]
    conn.close()


def test_read_only_status_latest_and_track_endpoints(monkeypatch, tmp_path):
    import api
    import config
    import telemetry
    from fastapi.testclient import TestClient
    base = dict(config.settings.__dict__)
    monkeypatch.setattr(config, "settings", SimpleNamespace(**{
        **base, **settings(tmp_path, mavlink_enabled=False).__dict__, "auth_enabled": False,
        "camera_id": "AIR-01", "camera_mode": "airborne",
    }))
    monkeypatch.setattr(api.worker, "start", lambda: None)
    monkeypatch.setattr(api.worker, "stop", lambda: None)
    telemetry._latest.clear(); telemetry._last_stored.clear()
    with TestClient(api.app) as client:
        assert client.get("/airborne/status").json()["state"] == "DISABLED"
        assert client.get("/airborne/telemetry/latest").status_code == 200
        mission = client.post("/airborne/missions", json={"name": "Track", "source_type": "live", "camera_id": "AIR-01"}).json()
        client.post(f"/airborne/missions/{mission['id']}/start")
        telemetry.ingest("AIR-01", {"timestamp": 200, "latitude": 21.1, "longitude": 72.1, "altitude_m": 99})
        track = client.get(f"/airborne/missions/{mission['id']}/track")
        assert track.status_code == 200 and track.json()[0]["latitude"] == 21.1
