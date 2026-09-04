"""Small JWT admin layer for trusted single-node deployments."""
from datetime import datetime, timedelta, timezone
import logging
import bcrypt
import jwt
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import config
logger = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)

def validate_auth_configuration() -> None:
    if config.settings.auth_enabled and not all((config.settings.jwt_secret, config.settings.admin_username, config.settings.admin_password_hash)):
        raise RuntimeError("AUTH_ENABLED requires JWT_SECRET, ADMIN_USERNAME, and ADMIN_PASSWORD_HASH")

def verify_password(password: str) -> bool:
    if not config.settings.admin_password_hash: return False
    try: return bcrypt.checkpw(password.encode(), config.settings.admin_password_hash.encode())
    except (ValueError, TypeError): return False

def create_token(username: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": username, "role": "admin", "iat": now, "exp": now + timedelta(minutes=config.settings.jwt_expiry_minutes)}, config.settings.jwt_secret, algorithm="HS256")

def require_admin(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), sentinel_session: str | None = Cookie(default=None)) -> str:
    if not config.settings.auth_enabled: return "local-anonymous"
    token = credentials.credentials if credentials else sentinel_session
    if not token: raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required", {"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, config.settings.jwt_secret, algorithms=["HS256"])
        if payload.get("sub") != config.settings.admin_username or payload.get("role") != "admin": raise ValueError("invalid role")
        return str(payload["sub"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token", {"WWW-Authenticate": "Bearer"})

def require_monitoring_access(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), sentinel_session: str | None = Cookie(default=None)) -> str:
    """Require admin only when surveillance read protection is explicitly enabled."""
    if not config.settings.auth_enabled or not config.settings.protect_monitoring_routes:
        return "monitoring-public"
    return require_admin(credentials, sentinel_session)
