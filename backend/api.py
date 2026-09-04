import logging, os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends, Response, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field
import config
from config import safe_source_label
import worker
from mavlink_service import service as mavlink_service
from stream import generate_frames
from storage import init_db, list_incidents, list_zones, upsert_zone, delete_zone, get_rule, set_rule
from auth import create_token, require_admin, require_monitoring_access, validate_auth_configuration, verify_password
from visual_intelligence.router import router as visual_intelligence_router
from airborne.router import router as airborne_router
from companion_router import router as companion_router
from airborne.recorded_analysis import recover_interrupted_jobs
from airborne import mission_monitor
logger = logging.getLogger(__name__); os.makedirs(config.settings.capture_directory, exist_ok=True)
@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = config.settings
    validate_auth_configuration(); init_db(settings.database_path); recover_interrupted_jobs(); mavlink_service.start(); worker.start(); mission_monitor.start()
    logger.info("API started auth_enabled=%s protect_monitoring_routes=%s camera_source=%s", settings.auth_enabled, settings.protect_monitoring_routes, safe_source_label(settings.camera_source))
    yield
    mission_monitor.stop(); mavlink_service.stop(); worker.stop(); logger.info("API stopped")
app = FastAPI(title="Smart Surveillance API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.settings.cors_origins, allow_credentials=True, allow_methods=["GET","POST","PUT","DELETE"], allow_headers=["Content-Type","Authorization","X-Telemetry-Key"])
app.include_router(visual_intelligence_router)
app.include_router(airborne_router)
app.include_router(companion_router)
@app.get("/health")
def health(): return {"ok":True}
@app.get("/auth/config")
def auth_config(): return {"auth_enabled": config.settings.auth_enabled}
class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)
@app.post("/auth/login")
def login(credentials: LoginRequest, response: Response):
    if not config.settings.auth_enabled: return {"access_token": None, "token_type": "bearer", "auth_enabled": False}
    if credentials.username != config.settings.admin_username or not verify_password(credentials.password):
        logger.warning("failed login username=%s", credentials.username)
        raise HTTPException(401, "Invalid username or password")
    token = create_token(credentials.username)
    response.set_cookie("sentinel_session", token, httponly=True, secure=config.settings.cookie_secure, samesite="lax", max_age=config.settings.jwt_expiry_minutes * 60)
    return {"access_token": token, "token_type": "bearer", "auth_enabled": True}
@app.get("/ready")
def ready(): return {"ready":True,"camera_online":worker.camera.online,"ai_online":worker.latest_status["ai_online"]}
@app.get("/")
def home(): return {"message":"Smart Surveillance API","health":"/health","docs":"/docs"}
@app.get("/video")
def video_feed(_access: str = Depends(require_monitoring_access)): return StreamingResponse(generate_frames(),media_type="multipart/x-mixed-replace; boundary=frame",headers={"Cache-Control":"no-store"})
@app.get("/status")
def status(_access: str = Depends(require_monitoring_access)): return worker.status()
@app.get("/alerts")
def alerts(_access: str = Depends(require_monitoring_access)): return {"active_alerts":[{"track_id":int(i),"duration_sec":round(float(d),2)} for i,d in worker.latest_alerts],"history":worker.alert_history[-20:]}
@app.get("/images")
def images(_access: str = Depends(require_monitoring_access)):
    result=[]
    for entry in os.scandir(config.settings.capture_directory):
        if entry.is_file() and entry.name.lower().endswith((".jpg",".jpeg",".png",".webp")): result.append({"filename":entry.name,"timestamp":datetime.fromtimestamp(entry.stat().st_mtime).isoformat(),"type":"Loitering"})
    return sorted(result,key=lambda item:item["timestamp"],reverse=True)[:200]
class Incident(BaseModel):
    id:int; created_at_ts:int; type:str; severity:str; message:str|None=None; camera:str|None=None; zone_id:int|None=None; track_id:int|None=None; duration_sec:float|None=None; screenshot_filename:str|None=None; telemetry:dict|None=None
@app.get("/incidents",response_model=list[Incident])
def incidents(limit:int=50,offset:int=0,type:str|None=None,severity:str|None=None,since_ts:int|None=None,_access: str = Depends(require_monitoring_access)): return list_incidents(config.settings.database_path,limit=limit,offset=offset,type=type,severity=severity,since_ts=since_ts)
@app.get("/cameras")
def cameras(_access: str = Depends(require_monitoring_access)):
    return [{"id":config.settings.camera_id,"name":config.settings.camera_name,"type":config.settings.camera_mode,"source":safe_source_label(config.settings.camera_source),"enabled":True}]
class AircraftTelemetryIn(BaseModel):
    timestamp:int=Field(ge=0); latitude:float=Field(ge=-90,le=90); longitude:float=Field(ge=-180,le=180)
    altitude_m:float=Field(ge=-500,le=20000); ground_speed_mps:float=Field(ge=0,le=500); heading_deg:float=Field(ge=0,le=360); battery_percent:float=Field(ge=0,le=100)
@app.post("/telemetry/aircraft/{camera_id}")
def aircraft_telemetry(camera_id: str, payload: AircraftTelemetryIn, x_telemetry_key: str|None=Header(default=None)):
    if not config.settings.airborne_telemetry_enabled: raise HTTPException(404,"Airborne telemetry is disabled")
    if camera_id != config.settings.camera_id or config.settings.camera_mode != "airborne": raise HTTPException(404,"Airborne camera not found")
    if not config.settings.airborne_telemetry_api_key or x_telemetry_key != config.settings.airborne_telemetry_api_key: raise HTTPException(401,"Invalid telemetry credentials")
    from telemetry import ingest
    return {"accepted":True,"telemetry":ingest(camera_id,payload.model_dump())}
@app.get("/telemetry/aircraft/{camera_id}")
def aircraft_telemetry_status(camera_id: str, _access: str = Depends(require_monitoring_access)):
    from telemetry import latest
    if camera_id != config.settings.camera_id or config.settings.camera_mode != "airborne": raise HTTPException(404,"Airborne camera not found")
    return {"camera_id":camera_id,"telemetry":latest(camera_id)}
@app.post("/cameras/{camera_id}/capture")
def capture_camera_frame(camera_id: str, _admin: str = Depends(require_admin)):
    if camera_id != config.settings.camera_id: raise HTTPException(404,"Camera not found")
    try: return worker.capture_current_frame()
    except RuntimeError as exc: raise HTTPException(409,str(exc))
class ZoneIn(BaseModel):
    id:int|None=None; name:str=Field(min_length=1,max_length=64); points:list[list[float]]=Field(min_length=3,max_length=100)
@app.get("/zones")
def zones(_access: str = Depends(require_monitoring_access)): return list_zones(config.settings.database_path)
@app.put("/zones")
def put_zone(zone:ZoneIn, _admin: str = Depends(require_admin)):
    points=[]
    for point in zone.points:
        if len(point)!=2 or not all(0<=float(value)<=1 for value in point): raise HTTPException(400,"Points must be normalized [x,y] values from 0 to 1")
        points.append([float(point[0]),float(point[1])])
    return upsert_zone(config.settings.database_path,zone.id,zone.name.strip(),points)
@app.delete("/zones/{zone_id}")
def remove_zone(zone_id:int, _admin: str = Depends(require_admin)): delete_zone(config.settings.database_path,zone_id); return {"ok":True}
class LoiterRule(BaseModel):
    enabled:bool=True; min_duration_sec:float=Field(default=10,ge=1,le=600); zone_id:int|None=None; cooldown_sec:float=Field(default=30,ge=0,le=3600)
@app.get("/rules/loitering")
def loiter_rule(_access: str = Depends(require_monitoring_access)): return get_rule(config.settings.database_path,"loitering") or LoiterRule().model_dump()
@app.put("/rules/loitering")
def put_loiter_rule(rule:LoiterRule, _admin: str = Depends(require_admin)): return set_rule(config.settings.database_path,"loitering",rule.model_dump())
@app.get("/outputs/{filename}")
def output_file(filename: str, _access: str = Depends(require_monitoring_access)):
    # Resolve both paths so a symlink inside the capture directory cannot escape it.
    if filename != Path(filename).name: raise HTTPException(404, "Not found")
    root = Path(config.settings.capture_directory).resolve()
    path = (root / filename).resolve()
    try: path.relative_to(root)
    except ValueError: raise HTTPException(404, "Not found")
    if not path.is_file(): raise HTTPException(404, "Not found")
    return FileResponse(path)
