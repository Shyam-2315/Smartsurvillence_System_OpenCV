from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

import config
from auth import require_admin, require_monitoring_access
from . import evidence, events, live_capture, live_investigation, recorded_analysis, recorded_investigation, reporting, service
from .schemas import ExtractFrameRequest, MissionCreate, MissionEvidenceOut, MissionEventOut, MissionOut
from mavlink_service import service as mavlink_service
from storage import list_mission_track

router = APIRouter(prefix="/airborne", tags=["Airborne Missions"])


@router.get("/status")
def airborne_status(_access: str = Depends(require_monitoring_access)):
    result = mavlink_service.status()
    result.update(camera_id=config.settings.airborne_camera_id, camera_name=config.settings.airborne_camera_name)
    return result


@router.get("/telemetry/latest")
def airborne_latest_telemetry(_access: str = Depends(require_monitoring_access)):
    from telemetry import latest
    return {"camera_id": config.settings.airborne_camera_id, "telemetry": latest(config.settings.airborne_camera_id), "mavlink": mavlink_service.status()}


@router.post("/missions", status_code=201, response_model=MissionOut)
def create_mission(payload: MissionCreate, _admin: str = Depends(require_admin)):
    return service.create_mission(**payload.model_dump())

@router.post("/missions/recorded", status_code=201, response_model=MissionOut)
async def create_recorded_mission(name: str = Form(...), video: UploadFile = File(...), notes: str | None = Form(None), _admin: str = Depends(require_admin)):
    return await service.create_recorded_mission(name=name, upload=video, notes=notes)

@router.get("/missions/recorded/{mission_id}", response_model=MissionOut)
def recorded_mission(mission_id: str, _access: str = Depends(require_monitoring_access)):
    result = service.get_mission(mission_id)
    if result["source_type"] != "recorded": raise HTTPException(404, "Recorded mission not found")
    return result

@router.post("/missions/recorded/{mission_id}/analyze", status_code=202)
def analyze_recorded_mission(mission_id: str, _admin: str = Depends(require_admin)):
    return recorded_analysis.start(mission_id)

@router.get("/missions/recorded/{mission_id}/analysis-status")
def recorded_analysis_status(mission_id: str, _access: str = Depends(require_monitoring_access)):
    return recorded_analysis.status(mission_id)

@router.post("/missions/recorded/{mission_id}/cancel")
def cancel_recorded_analysis(mission_id: str, _admin: str = Depends(require_admin)):
    return recorded_analysis.cancel(mission_id)


@router.post("/missions/{mission_id}/extract-frame", status_code=201)
def extract_recorded_frame(mission_id: str, payload: ExtractFrameRequest, _admin: str = Depends(require_admin)):
    return recorded_investigation.extract_frame(mission_id, payload.timestamp_seconds)


@router.post("/missions/{mission_id}/evidence/{evidence_id}/investigate", status_code=201)
def investigate_recorded_evidence(mission_id: str, evidence_id: str, _admin: str = Depends(require_admin)):
    return recorded_investigation.investigate_evidence(mission_id, evidence_id)


@router.post("/live/capture", status_code=201)
@router.post("/capture", status_code=201)
def capture_live_airborne_frame(_admin: str = Depends(require_admin)):
    return live_capture.capture()


@router.post("/evidence/{evidence_id}/investigate", status_code=201)
def investigate_live_airborne_evidence(evidence_id: str, _admin: str = Depends(require_admin)):
    return live_investigation.investigate(evidence_id)

@router.get("/missions/{mission_id}/video")
def recorded_video(mission_id: str, _access: str = Depends(require_monitoring_access)):
    return FileResponse(service.recorded_video_path(mission_id), media_type="video/*", filename="mission-video")


@router.get("/missions", response_model=list[MissionOut])
def missions(limit: int = 100, offset: int = 0, _access: str = Depends(require_monitoring_access)):
    return service.list_missions(limit=limit, offset=offset)


@router.get("/missions/{mission_id}", response_model=MissionOut)
def mission(mission_id: str, _access: str = Depends(require_monitoring_access)):
    return service.get_mission(mission_id)


@router.get("/missions/{mission_id}/track")
def mission_track(mission_id: str, _access: str = Depends(require_monitoring_access)):
    service.get_mission(mission_id)
    return list_mission_track(config.settings.database_path, mission_id)


@router.get("/missions/{mission_id}/summary")
def mission_summary(mission_id: str, _access: str = Depends(require_monitoring_access)):
    return reporting.summary(mission_id)


@router.get("/missions/{mission_id}/report")
def mission_report(mission_id: str, _access: str = Depends(require_monitoring_access)):
    return reporting.report(mission_id)


@router.post("/missions/{mission_id}/start", response_model=MissionOut)
def start_mission(mission_id: str, _admin: str = Depends(require_admin)):
    return service.transition_mission(mission_id, "active")


@router.post("/missions/{mission_id}/complete", response_model=MissionOut)
def complete_mission(mission_id: str, _admin: str = Depends(require_admin)):
    return service.transition_mission(mission_id, "completed")


@router.post("/missions/{mission_id}/abort", response_model=MissionOut)
def abort_mission(mission_id: str, _admin: str = Depends(require_admin)):
    return service.transition_mission(mission_id, "aborted")


@router.get("/missions/{mission_id}/events", response_model=list[MissionEventOut])
def mission_events(mission_id: str, _access: str = Depends(require_monitoring_access)):
    service.get_mission(mission_id)
    return events.list_for_mission(mission_id)


@router.get("/missions/{mission_id}/evidence", response_model=list[MissionEvidenceOut])
def mission_evidence(mission_id: str, _access: str = Depends(require_monitoring_access)):
    service.get_mission(mission_id)
    return evidence.list_for_mission(mission_id)


@router.get("/evidence/{evidence_id}/original")
def evidence_original(evidence_id: str, _access: str = Depends(require_monitoring_access)):
    path = evidence.original_path(evidence_id)
    return FileResponse(path, media_type="image/jpeg", filename=f"evidence-{evidence_id}.jpg")
