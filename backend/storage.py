import json
import os
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.abspath(os.path.join(BASE_DIR, "surveillance.db"))


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
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
            screenshot_filename TEXT
        )
        """
    )

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
    _upsert_rule(cur, "loitering", {"enabled": True, "min_duration_sec": 10, "zone_id": None, "cooldown_sec": 30})

    conn.commit()
    conn.close()


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
    created_at_ts: Optional[int] = None,
) -> Dict[str, Any]:
    created_at_ts = int(created_at_ts or time.time())
    conn = _connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO incidents (
            created_at_ts, type, severity, message, camera, zone_id, track_id, duration_sec, screenshot_filename
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        SELECT id, created_at_ts, type, severity, message, camera, zone_id, track_id, duration_sec, screenshot_filename
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
            }
        )
    return out

