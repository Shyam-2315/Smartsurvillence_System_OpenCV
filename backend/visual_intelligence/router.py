from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
import config
from auth import require_admin, require_monitoring_access
from storage import get_incident
from . import service
from .schemas import EnhanceRequest, RegionRequest, WebSearchRequest

router=APIRouter(prefix="/visual-intelligence", tags=["Visual Intelligence"])

@router.post("/analyze", status_code=201)
async def upload_and_analyze(image: UploadFile = File(...), _admin: str = Depends(require_admin)):
    data=await image.read(config.settings.visual_max_upload_mb*1024*1024+1)
    return service.analyze(service.create_bytes(data,image.filename or "upload.jpg")["id"])

@router.get("/analyses")
def analyses(limit:int=100, _access: str = Depends(require_monitoring_access)): return service.list_all(limit)

@router.get("/analyses/{analysis_id}")
def analysis(analysis_id:str, _access: str = Depends(require_monitoring_access)): return service.get(analysis_id)

@router.get("/web-status")
def web_status(_access: str = Depends(require_monitoring_access)):
    from . import search
    return search.status()

@router.post("/analyses/{analysis_id}/web-search")
def run_web_search(analysis_id: str, request: WebSearchRequest = WebSearchRequest(), _admin: str = Depends(require_admin)):
    return service.web_search(analysis_id, request.selected_text)

@router.delete("/analyses/{analysis_id}")
def remove(analysis_id:str, _admin: str = Depends(require_admin)): service.delete(analysis_id); return {"ok":True}

@router.post("/analyses/{analysis_id}/run")
def run(analysis_id:str, _admin: str = Depends(require_admin)): return service.analyze(analysis_id)

@router.post("/analyses/{analysis_id}/enhance")
def enhance(analysis_id:str, request:EnhanceRequest, _admin: str = Depends(require_admin)): return service.make_enhancement(analysis_id,request.model_dump())

@router.post("/analyses/{analysis_id}/regions/analyze", status_code=201)
def region(analysis_id:str, request:RegionRequest, _admin: str = Depends(require_admin)): return service.create_region(analysis_id,request.model_dump())

@router.post("/incidents/{incident_id}/analyze", status_code=201)
def incident_analysis(incident_id:int, _admin: str = Depends(require_admin)):
    incident=get_incident(config.settings.database_path,incident_id)
    if not incident or not incident.get("screenshot_filename"): raise HTTPException(404,"Incident screenshot not found")
    filename=Path(incident["screenshot_filename"]).name
    if filename != incident["screenshot_filename"]: raise HTTPException(404,"Incident screenshot not found")
    source=(Path(config.settings.capture_directory).resolve()/filename).resolve()
    if source.parent != Path(config.settings.capture_directory).resolve() or not source.is_file(): raise HTTPException(404,"Incident screenshot not found")
    context={"source_camera_id":incident.get("camera"),"capture_timestamp":incident.get("created_at_ts"),"telemetry":incident.get("telemetry")} if incident.get("camera") else {}
    return service.analyze(service.create_bytes(source.read_bytes(),filename,"incident",incident_id,source_metadata=context)["id"])

@router.get("/files/{relative_path:path}")
def evidence_file(relative_path:str, _access: str = Depends(require_monitoring_access)):
    path=service._safe(relative_path)
    if not path.is_file(): raise HTTPException(404,"Evidence file not found")
    return FileResponse(path)
