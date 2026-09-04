"""Phase 3 tests: analysis jobs use mocked shared inference, never GPU/network resources."""
import sqlite3
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import bcrypt
import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def make_video(tmp_path, frames=12, fps=4):
    path = tmp_path / f"{frames}.mp4"; writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (32, 24))
    for _ in range(frames): writer.write(np.zeros((24, 32, 3), dtype=np.uint8))
    writer.release(); return path.read_bytes()


@pytest.fixture
def analysis_client(monkeypatch, tmp_path):
    import api, config
    from fastapi.testclient import TestClient
    base = dict(config.settings.__dict__)
    monkeypatch.setattr(config, "settings", SimpleNamespace(**{**base, "database_path": str(tmp_path / "analysis.db"), "capture_directory": str(tmp_path / "outputs"), "recorded_mission_storage": str(tmp_path / "missions"), "recorded_analysis_sample_fps": 2, "recorded_analysis_max_concurrent_jobs": 1, "recorded_event_merge_gap_seconds": 2, "auth_enabled": False, "admin_username": "admin", "admin_password_hash": bcrypt.hashpw(b"password", bcrypt.gensalt()).decode(), "jwt_secret": "a-test-secret-long-enough-for-jwt"}))
    monkeypatch.setattr(api.worker, "start", lambda: None); monkeypatch.setattr(api.worker, "stop", lambda: None)
    return TestClient(api.app)


def upload(client, payload):
    response = client.post("/airborne/missions/recorded", data={"name": "Analysis flight"}, files={"video": ("flight.mp4", payload, "video/mp4")})
    assert response.status_code == 201, response.text; return response.json()["id"]


def wait_for(client, mission_id, terminal=True):
    for _ in range(100):
        result = client.get(f"/airborne/missions/recorded/{mission_id}/analysis-status").json()
        if not terminal or result["status"] in {"COMPLETED", "FAILED", "CANCELLED"}: return result
        time.sleep(.03)
    raise AssertionError("analysis did not finish")


def test_sampling_grouping_confidence_representative_evidence_and_shared_model(analysis_client, monkeypatch, tmp_path):
    import airborne.recorded_analysis as analysis
    import detection
    assert analysis.get_detections is detection.get_detections  # no second YOLO loader exists in this pipeline
    calls = []
    def fake(frame):
        calls.append(1); confidence = .4 + .1 * len(calls)
        return [([1, 2, 10, 10], confidence, "person")]
    monkeypatch.setattr(analysis, "get_detections", fake)
    with analysis_client as client:
        mission_id = upload(client, make_video(tmp_path))
        assert client.post(f"/airborne/missions/recorded/{mission_id}/analyze").status_code == 202
        job = wait_for(client, mission_id); assert job["status"] == "COMPLETED"
        assert job["frames_processed"] == 6 and job["estimated_samples"] == 6 and job["events_found"] == 1
        import config
        conn = sqlite3.connect(config.settings.database_path)
        samples = conn.execute("SELECT video_timestamp_seconds, frame_index, detections_json FROM recorded_frame_detections WHERE job_id=?", (job["id"],)).fetchall()
        event = conn.execute("SELECT object_class,start_seconds,end_seconds,peak_confidence,evidence_id FROM recorded_analysis_events WHERE job_id=?", (job["id"],)).fetchone(); conn.close()
        assert len(samples) == 6 and samples[0][1] == 0 and '"class": "person"' in samples[0][2]
        assert event[0] == "person" and event[1] == 0 and event[2] == pytest.approx(2.5) and event[3] == pytest.approx(1.0) and event[4]
        assert len(client.get(f"/airborne/missions/{mission_id}/evidence").json()) == 1


def test_gap_creates_multiple_events_and_analysis_failure(analysis_client, monkeypatch, tmp_path):
    import airborne.recorded_analysis as analysis
    hits = {"n": 0}
    def gapped(frame):
        hits["n"] += 1
        return [([0, 0, 2, 2], .8, "car")] if hits["n"] in {1, 6} else []
    monkeypatch.setattr(analysis, "get_detections", gapped)
    with analysis_client as client:
        mission_id = upload(client, make_video(tmp_path)); client.post(f"/airborne/missions/recorded/{mission_id}/analyze")
        assert wait_for(client, mission_id)["events_found"] == 2
        mission_id = upload(client, make_video(tmp_path, frames=4)); monkeypatch.setattr(analysis, "get_detections", lambda frame: (_ for _ in ()).throw(RuntimeError("inference failed")))
        client.post(f"/airborne/missions/recorded/{mission_id}/analyze")
        assert wait_for(client, mission_id)["status"] == "FAILED"


def test_job_cancel_concurrency_and_auth(analysis_client, monkeypatch, tmp_path):
    import airborne.recorded_analysis as analysis
    monkeypatch.setattr(analysis, "get_detections", lambda frame: (time.sleep(.05), [([0, 0, 2, 2], .9, "person")])[1])
    with analysis_client as client:
        one, two = upload(client, make_video(tmp_path, frames=80)), upload(client, make_video(tmp_path, frames=80))
        assert client.post(f"/airborne/missions/recorded/{one}/analyze").status_code == 202
        assert client.post(f"/airborne/missions/recorded/{two}/analyze").status_code == 202
        assert wait_for(client, two, terminal=False)["status"] == "QUEUED"  # max concurrent jobs is one
        assert client.post(f"/airborne/missions/recorded/{one}/cancel").json()["status"] == "CANCELLED"
        assert wait_for(client, one)["status"] == "CANCELLED"
        mission_id = upload(client, make_video(tmp_path))
        # Mutating analysis route is protected when auth is enabled.
        import config
        monkeypatch.setattr(config.settings, "auth_enabled", True)
        assert client.post(f"/airborne/missions/recorded/{mission_id}/analyze").status_code == 401


def test_restart_recovery_and_cancel_is_authoritative(analysis_client, monkeypatch, tmp_path):
    import airborne.recorded_analysis as analysis
    monkeypatch.setattr(analysis, "get_detections", lambda frame: (time.sleep(.08), [([0, 0, 2, 2], .9, "person")])[1])
    with analysis_client as client:
        mission_id = upload(client, make_video(tmp_path, frames=80))
        assert client.post(f"/airborne/missions/recorded/{mission_id}/analyze").status_code == 202
        # Cancel while inference is active.  The worker may finish its call, but
        # it must not persist a terminal COMPLETED state afterwards.
        time.sleep(.03)
        assert client.post(f"/airborne/missions/recorded/{mission_id}/cancel").json()["status"] == "CANCELLED"
        assert wait_for(client, mission_id)["status"] == "CANCELLED"

        import config
        conn = sqlite3.connect(config.settings.database_path)
        conn.execute("INSERT INTO missions (id,name,source_type,created_at,status,processing_status) VALUES ('interrupted','x','recorded','2020-01-01T00:00:00+00:00','planned','PROCESSING')")
        conn.execute("INSERT INTO recorded_analysis_jobs (id,mission_id,status,created_at) VALUES ('interrupted-job','interrupted','PROCESSING','2020-01-01T00:00:00+00:00')")
        conn.commit(); conn.close()
        analysis.recover_interrupted_jobs()
        conn = sqlite3.connect(config.settings.database_path)
        assert conn.execute("SELECT status FROM recorded_analysis_jobs WHERE id='interrupted-job'").fetchone()[0] == "FAILED"
        assert conn.execute("SELECT processing_status FROM missions WHERE id='interrupted'").fetchone()[0] == "FAILED"
        conn.close()


def test_live_status_and_video_stay_available_during_analysis(analysis_client, monkeypatch, tmp_path):
    import api
    import airborne.recorded_analysis as analysis
    monkeypatch.setattr(analysis, "get_detections", lambda frame: (time.sleep(.05), [([0, 0, 2, 2], .9, "person")])[1])
    monkeypatch.setattr(api, "generate_frames", lambda: iter([b"--frame\r\nContent-Type: image/jpeg\r\n\r\nframe\r\n"]))
    with analysis_client as client:
        mission_id = upload(client, make_video(tmp_path, frames=80))
        assert client.post(f"/airborne/missions/recorded/{mission_id}/analyze").status_code == 202
        assert client.get("/status").status_code == 200
        assert client.get("/video").status_code == 200
        client.post(f"/airborne/missions/recorded/{mission_id}/cancel")
