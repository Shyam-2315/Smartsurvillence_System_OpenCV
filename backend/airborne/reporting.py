"""Structured, factual mission summaries suitable for a later PDF renderer."""
from __future__ import annotations
from datetime import datetime, timezone
import sqlite3
from typing import Any
import config
from . import evidence, events, service
from storage import list_mission_track

def _conn():
    conn=sqlite3.connect(config.settings.database_path, timeout=10); conn.row_factory=sqlite3.Row; return conn

def _seconds(start: str | None, end: str | None) -> float | None:
    if not start: return None
    try:
        began=datetime.fromisoformat(start); finished=datetime.fromisoformat(end) if end else datetime.now(timezone.utc)
        return max(0, round((finished-began).total_seconds(), 2))
    except ValueError: return None

def _outage(rows: list[dict[str, Any]], lost: str, restored: str, end: str | None) -> tuple[float, float]:
    started=None; total=longest=0.0
    for row in reversed(rows):
        if row["event_type"] == lost: started=row["timestamp"]
        elif row["event_type"] == restored and started:
            duration=_seconds(started, row["timestamp"]) or 0; total+=duration; longest=max(longest,duration); started=None
    if started:
        duration=_seconds(started,end) or 0; total+=duration; longest=max(longest,duration)
    return round(total,2), round(longest,2)

def summary(mission_id: str) -> dict[str, Any]:
    mission=service.get_mission(mission_id); rows=events.list_for_mission(mission_id); items=evidence.list_for_mission(mission_id)
    conn=_conn()
    try: analyses=conn.execute("SELECT COUNT(*) FROM visual_analysis WHERE mission_id=?",(mission_id,)).fetchone()[0]
    finally: conn.close()
    duration=_seconds(mission.get("started_at") or mission.get("created_at"), mission.get("ended_at"))
    result={"mission_id":mission_id,"mission_duration_seconds":duration,"events":len(rows),"detections":sum(row["event_type"]=="recorded_detection" for row in rows),"evidence_count":len(items),"visual_intelligence_analyses":analyses}
    if mission["source_type"] == "live":
        video_loss, video_longest=_outage(rows,"video_lost","video_restored",mission.get("ended_at")); telemetry_loss, telemetry_longest=_outage(rows,"telemetry_stale","telemetry_restored",mission.get("ended_at"))
        result.update(video_availability_percent=None if duration is None else round(max(0,100*(duration-video_loss)/duration),2) if duration else 100.0, telemetry_availability_percent=None if duration is None else round(max(0,100*(duration-telemetry_loss)/duration),2) if duration else 100.0, disconnect_count=sum(row["event_type"]=="video_lost" for row in rows), longest_outage_seconds=max(video_longest,telemetry_longest))
    return result

def report(mission_id: str) -> dict[str, Any]:
    mission=service.get_mission(mission_id); rows=events.list_for_mission(mission_id); items=evidence.list_for_mission(mission_id)
    conn=_conn()
    try:
        analyses=[dict(row) for row in conn.execute("SELECT id,created_at,source_type,status,mission_event_id,evidence_id,video_timestamp_seconds FROM visual_analysis WHERE mission_id=? ORDER BY created_at",(mission_id,)).fetchall()]
    finally: conn.close()
    return {"report_version":"1.0","mission":mission,"summary":summary(mission_id),"video_metadata":{"duration_seconds":mission.get("duration_seconds"),"fps":mission.get("fps"),"width":mission.get("width"),"height":mission.get("height"),"frame_count":mission.get("frame_count"),"sha256":mission.get("original_video_sha256")},"track":list_mission_track(config.settings.database_path,mission_id),"events":rows,"evidence":items,"analyses":analyses}
