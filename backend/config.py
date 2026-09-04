"""Environment-backed application configuration."""
from __future__ import annotations
import logging, os, re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
# The root .env is the one used by both `scripts/start_backend.ps1` and Docker.
# Use it explicitly (rather than the process working directory), and make it the
# local deployment source of truth instead of silently retaining an old shell
# value.  In particular, a previous PowerShell session must not turn monitoring
# protection back on after an operator sets it off in .env.
ENV_FILE = PROJECT_DIR / ".env"
load_dotenv(ENV_FILE, override=True)

def parse_camera_source(value: str | None) -> int | str:
    value = (value or "0").strip()
    return int(value) if value.isdigit() else value

def parse_mavlink_connection(value: str | None) -> str:
    """Accept pymavlink UDP endpoints or an explicit serial device; never select a COM port implicitly."""
    connection = (value or "udpin:127.0.0.1:14551").strip()
    if not connection: raise ValueError("MAVLINK_CONNECTION cannot be empty")
    if re.fullmatch(r"COM[1-9][0-9]*", connection, re.IGNORECASE): return connection.upper()
    if connection.startswith(("udpin:", "udpout:", "udp:", "tcp:", "tcpin:", "tcpout:", "/dev/")): return connection
    raise ValueError("MAVLINK_CONNECTION must be a COM port (for example COM7) or a pymavlink UDP/TCP endpoint")

def safe_source_label(source: int | str) -> str:
    if isinstance(source, int): return str(source)
    parts = urlsplit(source)
    if not parts.scheme or not parts.netloc: return source
    host = parts.hostname or ""
    try: port = f":{parts.port}" if parts.port else ""
    except ValueError: port = ""
    return urlunsplit((parts.scheme, f"{host}{port}", parts.path, parts.query, ""))

def _origins(value: str) -> list[str]:
    return [v.strip().strip("[]'\"") for v in value.split(",") if v.strip().strip("[]'\"")]

def _project_path(value: str) -> str:
    return str((PROJECT_DIR / value).resolve()) if not os.path.isabs(value) else os.path.abspath(value)

@dataclass(frozen=True)
class Settings:
    camera_source: int | str; yolo_model: str; confidence_threshold: float; database_path: str; capture_directory: str
    bot_token: str | None; chat_id: str | None; telegram_enabled: bool; cors_origins: list[str]; log_level: str; camera_retry_seconds: float
    auth_enabled: bool; jwt_secret: str | None; jwt_expiry_minutes: int; admin_username: str | None; admin_password_hash: str | None; protect_monitoring_routes: bool; cookie_secure: bool
    visual_max_upload_mb: int = 15; image_super_resolution_enabled: bool = False; web_search_enabled: bool = False; web_search_provider: str = "disabled"; web_search_api_key: str | None = None; ocr_model_download_enabled: bool = False; web_search_max_queries: int = 3; web_search_results_per_query: int = 5; web_search_timeout_seconds: float = 8.0
    camera_id: str = "CAM-01"; camera_name: str = "Primary Camera"; camera_mode: str = "fixed"; airborne_telemetry_enabled: bool = False; airborne_telemetry_api_key: str | None = None; airborne_telemetry_store_interval_seconds: float = 2.0
    airborne_enabled: bool = False; airborne_camera_id: str = "AIR-01"; airborne_camera_name: str = "VAYU-X"; mavlink_enabled: bool = False; mavlink_connection: str = "udpin:127.0.0.1:14551"; mavlink_read_only: bool = True; mavlink_simulation_mode: bool = False; mavlink_heartbeat_timeout_seconds: float = 5.0; mavlink_reconnect_seconds: float = 3.0; mavlink_disconnect_seconds: float = 15.0; companion_health_enabled: bool = False; companion_health_api_key: str | None = None; airborne_telemetry_stale_seconds: float = 5.0; airborne_telemetry_association_max_seconds: float = 3.0
    recorded_mission_max_upload_mb: int = 2048; recorded_mission_storage: str = ""
    recorded_analysis_sample_fps: float = 2.0; recorded_analysis_max_concurrent_jobs: int = 1; recorded_event_merge_gap_seconds: float = 2.0
    @classmethod
    def from_env(cls) -> "Settings":
        confidence = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))
        if not 0 <= confidence <= 1: raise ValueError("CONFIDENCE_THRESHOLD must be between 0 and 1")
        return cls(parse_camera_source(os.getenv("CAMERA_SOURCE", "0")), _project_path(os.getenv("YOLO_MODEL", "backend/yolov8n.pt")), confidence,
            _project_path(os.getenv("DATABASE_PATH", "backend/surveillance.db")), _project_path(os.getenv("CAPTURE_DIRECTORY", "outputs")),
            os.getenv("BOT_TOKEN") or None, os.getenv("CHAT_ID") or None, os.getenv("TELEGRAM_ENABLED", "false").lower() in {"1","true","yes","on"},
            _origins(os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")), os.getenv("LOG_LEVEL", "INFO").upper(), max(.5, float(os.getenv("CAMERA_RETRY_SECONDS", "3"))),
            os.getenv("AUTH_ENABLED", "false").lower() in {"1","true","yes","on"}, os.getenv("JWT_SECRET") or None, max(1, int(os.getenv("JWT_EXPIRY_MINUTES", "480"))), os.getenv("ADMIN_USERNAME") or None, os.getenv("ADMIN_PASSWORD_HASH") or None,
            os.getenv("PROTECT_MONITORING_ROUTES", "false").lower() in {"1","true","yes","on"}, os.getenv("COOKIE_SECURE", "false").lower() in {"1","true","yes","on"},
            max(1, min(100, int(os.getenv("VISUAL_MAX_UPLOAD_MB", "15")))),
            os.getenv("IMAGE_SUPER_RESOLUTION_ENABLED", "false").lower() in {"1","true","yes","on"},
            os.getenv("WEB_SEARCH_ENABLED", "false").lower() in {"1","true","yes","on"},
            os.getenv("WEB_SEARCH_PROVIDER", "disabled").strip().lower(), os.getenv("WEB_SEARCH_API_KEY") or None,
            os.getenv("OCR_MODEL_DOWNLOAD_ENABLED", "false").lower() in {"1","true","yes","on"}, max(1, min(10, int(os.getenv("WEB_SEARCH_MAX_QUERIES", "3")))), max(1, min(20, int(os.getenv("WEB_SEARCH_RESULTS_PER_QUERY", "5")))), max(1.0, min(30.0, float(os.getenv("WEB_SEARCH_TIMEOUT_SECONDS", "8")))),
            os.getenv("CAMERA_ID", "CAM-01").strip()[:64], os.getenv("CAMERA_NAME", "Primary Camera").strip()[:128], os.getenv("CAMERA_MODE", "fixed").strip().lower() if os.getenv("CAMERA_MODE", "fixed").strip().lower() in {"fixed","airborne"} else "fixed",
            os.getenv("AIRBORNE_TELEMETRY_ENABLED", "false").lower() in {"1","true","yes","on"}, os.getenv("AIRBORNE_TELEMETRY_API_KEY") or None, max(.1, min(60.0, float(os.getenv("AIRBORNE_TELEMETRY_STORE_INTERVAL_SECONDS", "2")))),
            os.getenv("AIRBORNE_ENABLED", "false").lower() in {"1","true","yes","on"}, os.getenv("AIRBORNE_CAMERA_ID", "AIR-01").strip()[:64], os.getenv("AIRBORNE_CAMERA_NAME", "VAYU-X").strip()[:128],
            os.getenv("MAVLINK_ENABLED", "false").lower() in {"1","true","yes","on"}, parse_mavlink_connection(os.getenv("MAVLINK_CONNECTION", "udpin:127.0.0.1:14551"))[:512], os.getenv("MAVLINK_READ_ONLY", "true").lower() in {"1","true","yes","on"}, os.getenv("MAVLINK_SIMULATION_MODE", "false").lower() in {"1","true","yes","on"}, max(1.0, min(120.0, float(os.getenv("MAVLINK_HEARTBEAT_TIMEOUT_SECONDS", "5")))), max(.1, min(120.0, float(os.getenv("MAVLINK_RECONNECT_SECONDS", "3")))), max(1.0, min(600.0, float(os.getenv("MAVLINK_DISCONNECT_SECONDS", "15")))), os.getenv("COMPANION_HEALTH_ENABLED", "false").lower() in {"1","true","yes","on"}, os.getenv("COMPANION_HEALTH_API_KEY") or None, max(1.0, min(120.0, float(os.getenv("AIRBORNE_TELEMETRY_STALE_SECONDS", "5")))), max(.1, min(60.0, float(os.getenv("AIRBORNE_TELEMETRY_ASSOCIATION_MAX_SECONDS", "3")))),
            max(1, int(os.getenv("RECORDED_MISSION_MAX_UPLOAD_MB", "2048"))), _project_path(os.getenv("RECORDED_MISSION_STORAGE", "outputs/missions")),
            max(0.1, min(30.0, float(os.getenv("RECORDED_ANALYSIS_SAMPLE_FPS", "2")))), max(1, min(4, int(os.getenv("RECORDED_ANALYSIS_MAX_CONCURRENT_JOBS", "1")))), max(0.0, min(60.0, float(os.getenv("RECORDED_EVENT_MERGE_GAP_SECONDS", "2")))))

settings = Settings.from_env()

def reload_settings() -> Settings:
    """Rebuild the single runtime settings object after controlled test changes."""
    global settings
    settings = Settings.from_env()
    return settings
logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO), format="%(asctime)s %(levelname)s %(name)s %(message)s")
