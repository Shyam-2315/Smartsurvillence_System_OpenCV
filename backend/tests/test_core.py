import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import parse_camera_source, safe_source_label
from storage import create_incident, get_rule, init_db, list_incidents, set_rule
from geo import point_in_polygon

def test_camera_source_parsing_and_redaction():
    assert parse_camera_source("0") == 0
    assert parse_camera_source("01") == 1
    source = "rtsp://user:password@camera.local:554/stream"
    assert parse_camera_source(source) == source
    label = safe_source_label(source)
    assert label == "rtsp://camera.local:554/stream"
    assert "password" not in label

def test_database_persists_rule_and_incident():
    with tempfile.TemporaryDirectory() as directory:
        database = os.path.join(directory, "surveillance.db")
        init_db(database)
        set_rule(database, "loitering", {"enabled": False, "min_duration_sec": 12, "zone_id": None, "cooldown_sec": 4})
        init_db(database)
        assert get_rule(database, "loitering")["enabled"] is False
        create_incident(database, type="Loitering", severity="medium", message="test", created_at_ts=100)
        assert list_incidents(database)[0]["created_at_ts"] == 100

def test_zone_geometry():
    polygon = [(0, 0), (1, 0), (1, 1), (0, 1)]
    assert point_in_polygon((.5, .5), polygon)
    assert not point_in_polygon((1.2, .5), polygon)

def test_incident_filters_and_indexes():
    with tempfile.TemporaryDirectory() as directory:
        database=os.path.join(directory, "surveillance.db"); init_db(database)
        create_incident(database,type="Loitering",severity="high",message="a",created_at_ts=2)
        create_incident(database,type="Other",severity="low",message="b",created_at_ts=1)
        assert len(list_incidents(database,type="Loitering",severity="high")) == 1
        import sqlite3
        connection=sqlite3.connect(database)
        names={row[1] for row in connection.execute("PRAGMA index_list(incidents)")}
        connection.close()
        assert "idx_incidents_created_at" in names

def test_database_restart_preserves_incidents():
    with tempfile.TemporaryDirectory() as directory:
        database=os.path.join(directory, "surveillance.db"); init_db(database)
        create_incident(database,type="Loitering",severity="medium",message="a",created_at_ts=1); init_db(database)
        assert len(list_incidents(database)) == 1
