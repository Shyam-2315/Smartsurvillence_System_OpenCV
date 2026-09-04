import json
import os
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.abspath(os.path.join(BASE_DIR, "surveillance.db"))


def _connect(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    conn = _connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at_ts INTEGER NOT NULL,
            type TEXT NOT NULL,
            severity TEXT NOT NULL,
            message TEXT,
            camera TEXT,
            zone_id INTEGER,
            track_id INTEGER,
            duration_sec REAL,
            screenshot_filename TEXT,
            telemetry_json TEXT
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_incidents_created_at ON incidents(created_at_ts DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_incidents_type_severity ON incidents(type, severity)")
    columns={row[1] for row in cur.execute("PRAGMA table_info(incidents)")}
    if "telemetry_json" not in columns: cur.execute("ALTER TABLE incidents ADD COLUMN telemetry_json TEXT")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS visual_analysis (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, source_type TEXT NOT NULL,
            source_incident_id INTEGER, parent_analysis_id TEXT, original_filename TEXT NOT NULL,
            stored_original_path TEXT NOT NULL, sha256 TEXT NOT NULL, width INTEGER NOT NULL,
            height INTEGER NOT NULL, mime_type TEXT NOT NULL, status TEXT NOT NULL,
            error_message TEXT, enhancement_params_json TEXT NOT NULL DEFAULT '{}',
            ocr_json TEXT NOT NULL DEFAULT '[]', detections_json TEXT NOT NULL DEFAULT '[]',
            entities_json TEXT NOT NULL DEFAULT '{}', search_queries_json TEXT NOT NULL DEFAULT '[]',
            web_results_json TEXT NOT NULL DEFAULT '[]', summary_json TEXT NOT NULL DEFAULT '{}',
            metadata_json TEXT NOT NULL DEFAULT '{}'
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_visual_analysis_created ON visual_analysis(created_at DESC)")
    visual_columns = {row[1] for row in cur.execute("PRAGMA table_info(visual_analysis)")}
    for column, definition in {
        "mission_id": "TEXT", "mission_event_id": "TEXT", "evidence_id": "TEXT",
        "video_timestamp_seconds": "REAL",
    }.items():
        if column not in visual_columns: cur.execute(f"ALTER TABLE visual_analysis ADD COLUMN {column} {definition}")
    cur.execute("""CREATE TABLE IF NOT EXISTS aircraft_telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT, camera_id TEXT NOT NULL, timestamp INTEGER NOT NULL,
        latitude REAL NOT NULL, longitude REAL NOT NULL, altitude_m REAL, ground_speed_mps REAL,
        heading_deg REAL, battery_percent REAL)""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_aircraft_telemetry_camera_time ON aircraft_telemetry(camera_id, timestamp DESC)")
    telemetry_columns = {row[1] for row in cur.execute("PRAGMA table_info(aircraft_telemetry)")}
    for column, definition in {
        "mission_id": "TEXT", "relative_altitude_m": "REAL", "air_speed_mps": "REAL",
        "armed": "INTEGER", "flight_mode": "TEXT", "gps_fix": "INTEGER", "satellite_count": "INTEGER",
        "roll_deg": "REAL", "pitch_deg": "REAL", "yaw_deg": "REAL", "heartbeat_age_seconds": "REAL",
        "received_at": "REAL", "system_id": "INTEGER", "component_id": "INTEGER", "battery_voltage_v": "REAL",
        "battery_current_a": "REAL", "source": "TEXT",
    }.items():
        if column not in telemetry_columns: cur.execute(f"ALTER TABLE aircraft_telemetry ADD COLUMN {column} {definition}")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_aircraft_telemetry_mission_time ON aircraft_telemetry(mission_id, timestamp)")

    # Airborne mission foundation.  These tables are additive so existing
    # surveillance databases remain usable without a separate migration tool.
    cur.execute("""CREATE TABLE IF NOT EXISTS missions (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, source_type TEXT NOT NULL CHECK(source_type IN ('live', 'recorded')),
        camera_id TEXT, created_at TEXT NOT NULL, started_at TEXT, ended_at TEXT,
        status TEXT NOT NULL CHECK(status IN ('planned', 'active', 'completed', 'aborted')), notes TEXT
    )""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_missions_status ON missions(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_missions_created_at ON missions(created_at DESC)")
    # Additive recorded-mission fields for databases created before Phase 2.
    mission_columns = {row[1] for row in cur.execute("PRAGMA table_info(missions)")}
    for column, definition in {
        "original_video_path": "TEXT", "original_video_sha256": "TEXT", "duration_seconds": "REAL",
        "fps": "REAL", "width": "INTEGER", "height": "INTEGER", "frame_count": "INTEGER", "processing_status": "TEXT",
    }.items():
        if column not in mission_columns: cur.execute(f"ALTER TABLE missions ADD COLUMN {column} {definition}")
    cur.execute("""CREATE TABLE IF NOT EXISTS mission_events (
        id TEXT PRIMARY KEY, mission_id TEXT NOT NULL, timestamp TEXT NOT NULL, event_type TEXT NOT NULL,
        severity TEXT NOT NULL, camera_id TEXT, incident_id INTEGER, evidence_id TEXT, analysis_id TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE CASCADE
    )""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_mission_events_mission_time ON mission_events(mission_id, timestamp DESC)")
    cur.execute("""CREATE TABLE IF NOT EXISTS mission_evidence (
        id TEXT PRIMARY KEY, mission_id TEXT, camera_id TEXT, created_at TEXT NOT NULL, capture_timestamp TEXT NOT NULL,
        source_type TEXT NOT NULL, original_path TEXT NOT NULL, sha256 TEXT NOT NULL, incident_id INTEGER,
        analysis_id TEXT, latitude REAL, longitude REAL, altitude_m REAL, heading_deg REAL,
        telemetry_associated INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE SET NULL
    )""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_mission_evidence_mission ON mission_evidence(mission_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_mission_evidence_created_at ON mission_evidence(created_at DESC)")
    evidence_columns = {row[1] for row in cur.execute("PRAGMA table_info(mission_evidence)")}
    if "metadata_json" not in evidence_columns: cur.execute("ALTER TABLE mission_evidence ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'")
    cur.execute("""CREATE TABLE IF NOT EXISTS recorded_analysis_jobs (
        id TEXT PRIMARY KEY, mission_id TEXT NOT NULL UNIQUE, status TEXT NOT NULL,
        progress_percent REAL NOT NULL DEFAULT 0, frames_processed INTEGER NOT NULL DEFAULT 0,
        estimated_samples INTEGER NOT NULL DEFAULT 0, events_found INTEGER NOT NULL DEFAULT 0,
        error_message TEXT, created_at TEXT NOT NULL, started_at TEXT, ended_at TEXT,
        FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE CASCADE)""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_recorded_analysis_jobs_status ON recorded_analysis_jobs(status)")
    cur.execute("""CREATE TABLE IF NOT EXISTS recorded_frame_detections (
        id TEXT PRIMARY KEY, job_id TEXT NOT NULL, video_timestamp_seconds REAL NOT NULL,
        frame_index INTEGER NOT NULL, detections_json TEXT NOT NULL,
        FOREIGN KEY(job_id) REFERENCES recorded_analysis_jobs(id) ON DELETE CASCADE)""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_recorded_frame_detections_job_time ON recorded_frame_detections(job_id, video_timestamp_seconds)")
    cur.execute("""CREATE TABLE IF NOT EXISTS recorded_analysis_events (
        id TEXT PRIMARY KEY, job_id TEXT NOT NULL, mission_id TEXT NOT NULL, object_class TEXT NOT NULL,
        start_seconds REAL NOT NULL, end_seconds REAL NOT NULL, peak_confidence REAL NOT NULL,
        representative_frame_index INTEGER NOT NULL, evidence_id TEXT,
        FOREIGN KEY(job_id) REFERENCES recorded_analysis_jobs(id) ON DELETE CASCADE,
        FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE CASCADE,
        FOREIGN KEY(evidence_id) REFERENCES mission_evidence(id) ON DELETE SET NULL)""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_recorded_analysis_events_job ON recorded_analysis_events(job_id)")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS zones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            points_json TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS rules (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL
        )
        """
    )

    conn.commit()

    # Defaults (idempotent)
    existing = cur.execute("SELECT COUNT(*) AS c FROM zones").fetchone()["c"]
    if int(existing) == 0:
        full_frame = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
        cur.execute(
            "INSERT INTO zones (name, points_json) VALUES (?, ?)",
            ("Full Frame", json.dumps(full_frame)),
        )

    # Rules are stored as JSON so we can extend later without migrations.
    cur.execute("INSERT OR IGNORE INTO rules (key, value_json) VALUES (?, ?)", ("loitering", json.dumps({"enabled": True, "min_duration_sec": 10, "zone_id": None, "cooldown_sec": 30})))

    conn.commit()
    conn.close()

def store_telemetry(db_path: str, sample: Dict[str, Any]) -> None:
    conn=_connect(db_path); conn.execute("""INSERT INTO aircraft_telemetry (camera_id,timestamp,latitude,longitude,altitude_m,ground_speed_mps,heading_deg,battery_percent,mission_id,relative_altitude_m,air_speed_mps,armed,flight_mode,gps_fix,satellite_count,roll_deg,pitch_deg,yaw_deg,heartbeat_age_seconds,received_at,system_id,component_id,battery_voltage_v,battery_current_a,source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(sample["camera_id"],sample["timestamp"],sample["latitude"],sample["longitude"],sample.get("altitude_m"),sample.get("ground_speed_mps"),sample.get("heading_deg"),sample.get("battery_remaining_percent",sample.get("battery_percent")),sample.get("mission_id"),sample.get("relative_altitude_m"),sample.get("air_speed_mps"),sample.get("armed"),sample.get("flight_mode"),sample.get("gps_fix_type",sample.get("gps_fix")),sample.get("satellites_visible",sample.get("satellite_count")),sample.get("roll_deg"),sample.get("pitch_deg"),sample.get("yaw_deg"),sample.get("heartbeat_age_seconds"),sample.get("received_at"),sample.get("system_id"),sample.get("component_id"),sample.get("battery_voltage_v"),sample.get("battery_current_a"),sample.get("source"))); conn.commit(); conn.close()

def list_mission_track(db_path: str, mission_id: str) -> List[Dict[str, Any]]:
    conn=_connect(db_path); rows=conn.execute("SELECT timestamp,latitude,longitude,altitude_m FROM aircraft_telemetry WHERE mission_id=? AND latitude IS NOT NULL AND longitude IS NOT NULL ORDER BY timestamp ASC,id ASC",(mission_id,)).fetchall(); conn.close()
    return [dict(row) for row in rows]


def get_incident(db_path: str, incident_id: int) -> Optional[Dict[str, Any]]:
    conn = _connect(db_path)
    row = conn.execute("SELECT * FROM incidents WHERE id = ?", (int(incident_id),)).fetchone()
    conn.close()
    return dict(row) if row else None


def _upsert_rule(cur: sqlite3.Cursor, key: str, value: Dict[str, Any]) -> None:
    cur.execute(
        """
        INSERT INTO rules (key, value_json)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json
        """,
        (key, json.dumps(value)),
    )


def get_rule(db_path: str, key: str) -> Optional[Dict[str, Any]]:
    conn = _connect(db_path)
    row = conn.execute("SELECT value_json FROM rules WHERE key = ?", (key,)).fetchone()
    conn.close()
    if not row:
        return None
    try:
        return json.loads(row["value_json"])
    except Exception:
        return None


def set_rule(db_path: str, key: str, value: Dict[str, Any]) -> Dict[str, Any]:
    conn = _connect(db_path)
    cur = conn.cursor()
    _upsert_rule(cur, key, value)
    conn.commit()
    conn.close()
    return value


def list_zones(db_path: str) -> List[Dict[str, Any]]:
    conn = _connect(db_path)
    rows = conn.execute("SELECT id, name, points_json FROM zones ORDER BY id ASC").fetchall()
    conn.close()
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append({"id": int(r["id"]), "name": r["name"], "points": json.loads(r["points_json"])})
    return out


def upsert_zone(db_path: str, zone_id: Optional[int], name: str, points: List[List[float]]) -> Dict[str, Any]:
    conn = _connect(db_path)
    cur = conn.cursor()
    if zone_id is None:
        cur.execute(
            "INSERT INTO zones (name, points_json) VALUES (?, ?)",
            (name, json.dumps(points)),
        )
        zone_id = int(cur.lastrowid)
    else:
        cur.execute(
            "UPDATE zones SET name = ?, points_json = ? WHERE id = ?",
            (name, json.dumps(points), int(zone_id)),
        )
    conn.commit()
    conn.close()
    return {"id": int(zone_id), "name": name, "points": points}


def delete_zone(db_path: str, zone_id: int) -> None:
    conn = _connect(db_path)
    conn.execute("DELETE FROM zones WHERE id = ?", (int(zone_id),))
    conn.commit()
    conn.close()


def create_incident(
    db_path: str,
    *,
    type: str,
    severity: str,
    message: str,
    camera: Optional[str] = None,
    zone_id: Optional[int] = None,
    track_id: Optional[int] = None,
    duration_sec: Optional[float] = None,
    screenshot_filename: Optional[str] = None,
    created_at_ts: Optional[int] = None, telemetry: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    created_at_ts = int(created_at_ts or time.time())
    conn = _connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO incidents (
            created_at_ts, type, severity, message, camera, zone_id, track_id, duration_sec, screenshot_filename, telemetry_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(created_at_ts),
            str(type),
            str(severity),
            str(message),
            camera,
            int(zone_id) if zone_id is not None else None,
            int(track_id) if track_id is not None else None,
            float(duration_sec) if duration_sec is not None else None,
            screenshot_filename,
            json.dumps(telemetry) if telemetry else None,
        ),
    )
    incident_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return {
        "id": incident_id,
        "created_at_ts": created_at_ts,
        "type": type,
        "severity": severity,
        "message": message,
        "camera": camera,
        "zone_id": zone_id,
        "track_id": track_id,
        "duration_sec": duration_sec,
        "screenshot_filename": screenshot_filename,
        "telemetry": telemetry,
    }


def list_incidents(
    db_path: str,
    *,
    limit: int = 50,
    offset: int = 0,
    type: Optional[str] = None,
    severity: Optional[str] = None,
    since_ts: Optional[int] = None,
) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))

    where: List[str] = []
    params: List[Any] = []
    if type:
        where.append("type = ?")
        params.append(str(type))
    if severity:
        where.append("severity = ?")
        params.append(str(severity))
    if since_ts is not None:
        where.append("created_at_ts >= ?")
        params.append(int(since_ts))

    clause = (" WHERE " + " AND ".join(where)) if where else ""

    conn = _connect(db_path)
    rows = conn.execute(
        f"""
        SELECT id, created_at_ts, type, severity, message, camera, zone_id, track_id, duration_sec, screenshot_filename, telemetry_json
        FROM incidents
        {clause}
        ORDER BY created_at_ts DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (*params, limit, offset),
    ).fetchall()
    conn.close()

    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": int(r["id"]),
                "created_at_ts": int(r["created_at_ts"]),
                "type": r["type"],
                "severity": r["severity"],
                "message": r["message"],
                "camera": r["camera"],
                "zone_id": int(r["zone_id"]) if r["zone_id"] is not None else None,
                "track_id": int(r["track_id"]) if r["track_id"] is not None else None,
                "duration_sec": float(r["duration_sec"]) if r["duration_sec"] is not None else None,
                "screenshot_filename": r["screenshot_filename"],
                "telemetry": json.loads(r["telemetry_json"]) if r["telemetry_json"] else None,
            }
        )
    return out
