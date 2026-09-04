import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bcrypt
import auth

@pytest.fixture
def secured(monkeypatch):
    import config
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-must-be-at-least-thirty-two-bytes")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", bcrypt.hashpw(b"correct", bcrypt.gensalt()).decode())
    settings = config.reload_settings()
    yield settings
    monkeypatch.undo()
    config.reload_settings()

def test_password_and_token_round_trip(secured):
    assert auth.verify_password("correct")
    assert not auth.verify_password("wrong")
    token = auth.create_token("admin")
    from fastapi.security import HTTPAuthorizationCredentials
    assert auth.require_admin(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)) == "admin"

def test_missing_or_bad_token_rejected(secured):
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials
    with pytest.raises(HTTPException): auth.require_admin(None)
    with pytest.raises(HTTPException): auth.require_admin(HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad"))

def test_enabled_auth_requires_complete_configuration(monkeypatch):
    import config
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD_HASH", raising=False)
    config.reload_settings()
    with pytest.raises(RuntimeError): auth.validate_auth_configuration()
